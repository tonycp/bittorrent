from __future__ import annotations
from typing import Any, Dict

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

import logging

logger = logging.getLogger(__name__)


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

        vc = await self._vc_cache.get_or_fetch(tracker_id, fetch_vc)

        return vc if vc else VectorClock(clock={tracker_id: 0})

    def _should_apply(self, local_vc: VectorClock, remote_vc: VectorClock) -> bool:
        """Valida orden causal: retorna True si remote_vc puede aplicarse"""
        # Aplicar si: local_vc <= remote_vc (existe causalidad)
        return local_vc <= remote_vc

    # hdl_key: "Event:get:last_event"
    @get(dtos.GET_LAST_EVENT_DATASET)
    async def get_last_event(self, tracker_id: str) -> EventLog:
        """Obtiene último evento de un tracker"""
        return await self.event_repo.get_latest_by_tracker(tracker_id=tracker_id)

    # hdl_key: "Event:get:pending_events"
    @get()
    async def pending_events(self):
        """Obtiene eventos pendientes de replicación para este tracker"""
        try:
            import os
            from src.models import EventLog

            tracker_id = os.getenv("TRACKER_ID", "tracker-unknown")

            # Obtener eventos recientes que aún no han sido marcados como replicados
            events = await self.event_repo.get_pending_replication_for_tracker(
                target_tracker_id="*",  # Todos los trackers
                since_timestamp=0,
            )

            if not events:
                logger.debug(f"[{tracker_id}] No pending events found")
                return {"events": []}

            logger.info(f"[{tracker_id}] Found {len(events)} pending events")
            
            # Convertir EventTable (SQLAlchemy) a EventLog (Pydantic) y luego a dict
            events_data = []
            for ev in events:
                event_model = EventLog.model_validate(ev)
                events_data.append(event_model.model_dump())

            return {"events": events_data}
        except Exception as e:
            logger.error(f"Error getting pending events: {e}", exc_info=True)
            return {"events": []}

    # hdl_key: "Event:create:event"
    @create(dtos.CREATE_EVENT_DATASET)
    async def create_event(
        self,
        tracker_id: str,
        operation: str,
        data: Dict[str, Any],
    ):
        """Crea evento local (genérico para cualquier operación)"""
        logger.info(
            f"[{tracker_id}] create_event called: operation={operation}"
        )

        try:
            from src.schemas import EventTable
            
            current_vc = await self.get_current_vc(tracker_id)
            current_vc.increment(tracker_id)

            event = EventTable(
                tracker_id=tracker_id,
                vector_clock=current_vc.clock,  # dict format for JSON
                operation=operation,  # "peer_announce", "peer_stopped", etc.
                timestamp=current_vc.get(tracker_id),
                data=data,
            )

            event = await self.event_repo.add(event)
            
            # Flush para asignar ID
            await self.event_repo.session.flush()
            
            # Ahora el event tiene id, created_at, updated_at
            logger.info(f"[{tracker_id}] Event after flush: id={event.id}, created_at={event.created_at}")

            # Invalidar caché después de crear evento
            await self._vc_cache.invalidate(tracker_id)

            # Convertir EventTable a dict para EventSuccess
            from src.models import EventLog
            event_model = EventLog.model_validate(event)
            
            # Retornar evento completo
            return EventSuccess(request=event_model.model_dump())
        except Exception as e:
            logger.error(f"[{tracker_id}] ERROR in create_event: {e}")
            import traceback
            logger.error(f"[{tracker_id}] Traceback: {traceback.format_exc()}")
            raise

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
