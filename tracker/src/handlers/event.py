from __future__ import annotations
from typing import Any, Dict

from dependency_injector.wiring import Provide

from bit_lib.models import EventSuccess
from bit_lib.handlers import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.handlers.crud import get, create, update
from bit_lib.errors import ServiceError

from src.models import EventLog
from src.repos import RepoContainer, EventLogRepository

from . import dtos


@controller("Event")
class EventHandler(BaseHandler):
    def __init__(
        self,
        event_repo: EventLogRepository = Provide[RepoContainer.event_log_repo],
    ):
        super().__init__()
        self.event_repo = event_repo
        self._cached_vc_by_tracker: Dict[str, Dict[str, int]] = {}

    async def get_current_vc(self, tracker_id: str) -> Dict[str, int]:
        """Obtiene VC actual para un tracker concreto desde su último evento"""
        if tracker_id in self._cached_vc_by_tracker:
            return dict(self._cached_vc_by_tracker[tracker_id])

        last_event = await self.event_repo.get_latest_by_tracker(tracker_id)
        if last_event:
            vc = dict(last_event.vector_clock)
        else:
            vc = {tracker_id: 0}

        self._cached_vc_by_tracker[tracker_id] = vc
        return dict(vc)

    def _cache_vc(self, tracker_id: str, vc: Dict[str, int]):
        self._cached_vc_by_tracker[tracker_id] = dict(vc)

    def _should_apply(
        self, local_vc: Dict[str, int], remote_vc: Dict[str, int]
    ) -> bool:
        """Valida orden causal"""
        keys = set(remote_vc) | set(local_vc)
        less_or_equal = all(local_vc.get(k, 0) <= remote_vc.get(k, 0) for k in keys)
        strictly_less = any(local_vc.get(k, 0) < remote_vc.get(k, 0) for k in keys)
        return less_or_equal and strictly_less

    # hdl_key: "Event:get:last_event"
    @get(dtos.GET_LAST_EVENT_DATASET)
    async def get_last_event(self, tracker_id: str) -> EventLog:
        """Obtiene último evento de un tracker"""
        return await self.event_repo.get_latest_by_tracker(tracker_id=tracker_id)

    # hdl_key: "Event:create:event"
    @create(dtos.CREATE_EVENT_DATASET)
    async def create_event(
        self,
        tracker_id: str,
        operation: str,
        data: Dict[str, Any],
    ):
        """Crea evento local (genérico para cualquier operación)"""
        current_vc = await self.get_current_vc(tracker_id)
        current_vc[tracker_id] = current_vc.get(tracker_id, 0) + 1

        event = EventLog(
            tracker_id=tracker_id,
            vector_clock=current_vc,
            operation=operation,  # "peer_announce", "peer_stopped", etc.
            timestamp=current_vc[tracker_id],
            data=data,
        )

        await self.event_repo.add(event)
        self._cache_vc(tracker_id, current_vc)

        # Retornar evento para replicación
        return EventSuccess(request=event.model_dump())

    # hdl_key: "Event:update:event"
    @update(dtos.APPLY_EVENT_DATASET)
    async def apply_event(
        self,
        tracker_id: str,
        vector_clock: Dict[str, int],
        operation: str,
        timestamp: int,
        data: Dict[str, Any],
    ):
        """Aplica evento remoto (valida VC y delega a ReplicationHandler)"""
        event = EventLog(
            tracker_id=tracker_id,
            vector_clock=vector_clock,
            operation=operation,
            timestamp=timestamp,
            data=data,
        )

        # Validar orden causal
        current_vc = await self.get_current_vc(tracker_id)
        if not self._should_apply(current_vc, event.vector_clock):
            raise ServiceError(
                details={
                    "reason": "event out of order",
                    "local_vc": current_vc,
                    "remote_vc": event.vector_clock,
                }
            )

        # Actualizar cache local con VC remoto aplicado
        self._cache_vc(tracker_id, event.vector_clock)

        # Retornar evento para ReplicationHandler
        return EventSuccess(request=event.model_dump())
