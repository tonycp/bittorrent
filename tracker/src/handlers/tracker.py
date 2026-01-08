"""Handler para operaciones del registro distribuido de trackers"""

from bit_lib.handlers.crud import create, get, update, delete
from bit_lib.handlers.hander import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.context import VectorClock
from bit_lib.models import DataResponse

from src.repos import TrackerRepository, RepoContainer
from src.models.tracker import Tracker
from dependency_injector.wiring import Closing, Provide

from . import dtos


@controller("Tracker")
class TrackerHandler(BaseHandler):
    def __init__(
        self,
        tracker_repo: TrackerRepository = Closing[Provide[RepoContainer.tracker_repo]],
    ):
        super().__init__()
        self.tracker_repo = tracker_repo

    @create(dtos.REGISTER_TRACKER_DATASET)
    async def register_tracker(
        self,
        tracker_id: str,
        host: str,
        port: int,
        status: str = "online",
        vector_clock: dict = None,
    ):
        """Registra o actualiza un tracker en la red distribuida"""
        vc = VectorClock.from_dict(vector_clock) if vector_clock else VectorClock()

        tracker = Tracker(
            tracker_id=tracker_id,
            host=host,
            port=port,
            status=status,
            vector_clock=vc,
        )

        await self.tracker_repo.upsert(tracker)

        return DataResponse(
            data={
                "tracker_id": tracker_id,
                "status": "registered",
                "vector_clock": vc.to_dict(),
            }
        )

    @get(dtos.GET_TRACKER_DATASET)
    async def get_tracker(self, tracker_id: str):
        """Obtiene información de un tracker específico"""
        tracker = await self.tracker_repo.get_by_tracker_id(tracker_id)

        if not tracker:
            raise ValueError(f"Tracker {tracker_id} no encontrado")

        return DataResponse(
            data={
                "tracker_id": tracker.tracker_id,
                "host": tracker.host,
                "port": tracker.port,
                "status": tracker.status,
                "vector_clock": tracker.vector_clock.to_dict(),
                "created_at": tracker.created_at.isoformat()
                if tracker.created_at
                else None,
                "updated_at": tracker.updated_at.isoformat()
                if tracker.updated_at
                else None,
            }
        )

    @get(dtos.GET_ACTIVE_TRACKERS_DATASET)
    async def get_active_trackers(self, ttl_minutes: int = 30):
        """Obtiene lista de trackers activos en la red"""
        trackers = await self.tracker_repo.get_active_trackers(ttl_minutes)

        return DataResponse(
            data={
                "count": len(trackers),
                "trackers": [
                    {
                        "tracker_id": t.tracker_id,
                        "host": t.host,
                        "port": t.port,
                        "status": t.status,
                        "vector_clock": t.vector_clock.to_dict(),
                    }
                    for t in trackers
                ],
            }
        )

    @get(dtos.GET_ALL_TRACKERS_DATASET)
    async def get_all_trackers(self):
        """Obtiene todos los trackers registrados"""
        trackers = await self.tracker_repo.get_all()

        return DataResponse(
            data={
                "count": len(trackers),
                "trackers": [
                    {
                        "tracker_id": t.tracker_id,
                        "host": t.host,
                        "port": t.port,
                        "status": t.status,
                        "vector_clock": t.vector_clock.to_dict(),
                        "updated_at": t.updated_at.isoformat()
                        if t.updated_at
                        else None,
                    }
                    for t in trackers
                ],
            }
        )

    @update(dtos.UPDATE_LAST_SEEN_DATASET)
    async def update_last_seen(self, tracker_id: str):
        """Actualiza el timestamp de última actividad de un tracker"""
        await self.tracker_repo.update_last_seen(tracker_id)

        return DataResponse(
            data={
                "tracker_id": tracker_id,
                "status": "updated",
            }
        )

    @update(dtos.MARK_INACTIVE_DATASET)
    async def mark_inactive(self, tracker_id: str):
        """Marca un tracker como inactivo"""
        await self.tracker_repo.mark_inactive(tracker_id)

        return DataResponse(
            data={
                "tracker_id": tracker_id,
                "status": "inactive",
            }
        )

    @delete(dtos.REMOVE_DEAD_TRACKERS_DATASET)
    async def remove_dead_trackers(self, ttl_minutes: int = 60):
        """Elimina trackers muertos o inactivos por mucho tiempo"""
        count = await self.tracker_repo.remove_dead_trackers(ttl_minutes)

        return DataResponse(
            data={
                "removed_count": count,
                "ttl_minutes": ttl_minutes,
            }
        )
