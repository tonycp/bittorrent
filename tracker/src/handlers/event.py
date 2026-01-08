from __future__ import annotations
from typing import Any, Dict, Optional

from dependency_injector.wiring import Provide

from bit_lib.models import EventSuccess
from bit_lib.handlers import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.handlers.crud import get, create, update
from bit_lib.errors import ServiceError
from bit_lib.context import CacheManager, VectorClock

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
        
        # Caché de VectorClock por tracker con TTL de 30s
        self._vc_cache = CacheManager(default_ttl=30, name="event_vc_cache")

    async def get_current_vc(self, tracker_id: str) -> VectorClock:
        """Obtiene VectorClock actual para un tracker desde su último evento"""
        async def fetch_vc() -> VectorClock:
            """Fetch function que obtiene VC del último evento"""
            recent_event = await self.event_repo.get_latest_by_tracker(tracker_id)
            if recent_event:
                return recent_event.vector_clock
            else:
                return VectorClock(clock={tracker_id: 0})
        
        vc = await self._vc_cache.get_or_fetch(
            tracker_id,
            fetch_vc
        )
        
        return vc if vc else VectorClock(clock={tracker_id: 0})

    def _should_apply(
        self, local_vc: VectorClock, remote_vc: VectorClock
    ) -> bool:
        """Valida orden causal: retorna True si remote_vc puede aplicarse"""
        # Aplicar si: local_vc <= remote_vc (existe causalidad)
        return local_vc <= remote_vc

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
        current_vc.increment(tracker_id)

        event = EventLog(
            tracker_id=tracker_id,
            vector_clock=current_vc,
            operation=operation,  # "peer_announce", "peer_stopped", etc.
            timestamp=current_vc.get(tracker_id),
            data=data,
        )

        await self.event_repo.add(event)
        
        # Invalidar caché después de crear evento
        await self._vc_cache.invalidate(tracker_id)
        await self._vc_cache.invalidate(tracker_id)

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
        # Convertir Dict a VectorClock
        remote_vc = VectorClock.from_dict(vector_clock)
        
        event = EventLog(
            tracker_id=tracker_id,
            vector_clock=remote_vc,
            operation=operation,
            timestamp=timestamp,
            data=data,
        )

        # Validar orden causal
        current_vc = await self.get_current_vc(tracker_id)
        if not self._should_apply(current_vc, remote_vc):
            raise ServiceError(
                details={
                    "reason": "event out of order",
                    "local_vc": current_vc.to_dict(),
                    "remote_vc": remote_vc.to_dict(),
                }
            )

        # Invalidar caché después de aplicar evento remoto
        await self._vc_cache.invalidate(tracker_id)

        # Retornar evento para ReplicationHandler
        return EventSuccess(request=event.model_dump())
