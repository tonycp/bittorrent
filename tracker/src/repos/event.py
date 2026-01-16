from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import select, delete
from typing import List

from src.schemas import EventTable


class EventLogRepository(SQLAlchemyAsyncRepository[EventTable]):
    model_type = EventTable

    async def get_since_version(
        self, tracker_id: str, min_version: int
    ) -> List[EventTable]:
        stmt = select(EventTable).where(
            EventTable.tracker_id == tracker_id,
            EventTable.vector_clock[tracker_id].astext.cast(int) > min_version,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_operation(self, operation: str) -> List[EventTable]:
        stmt = select(EventTable).where(EventTable.operation == operation)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_torrent(self, torrent_id: str) -> List[EventTable]:
        stmt = select(EventTable).where(
            EventTable.data["torrent_id"].astext == torrent_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_replication(
        self, last_replicated_timestamp: int
    ) -> List[EventTable]:
        stmt = (
            select(EventTable)
            .where(EventTable.timestamp > last_replicated_timestamp)
            .order_by(EventTable.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_events_between(
        self, start_timestamp: int, end_timestamp: int
    ) -> List[EventTable]:
        stmt = (
            select(EventTable)
            .where(
                EventTable.timestamp >= start_timestamp,
                EventTable.timestamp <= end_timestamp,
            )
            .order_by(EventTable.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def purge_old_events(self, before_timestamp: int) -> int:
        stmt = delete(EventTable).where(EventTable.timestamp < before_timestamp)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_latest_by_tracker(self, tracker_id: str) -> EventTable | None:
        stmt = (
            select(EventTable)
            .where(EventTable.tracker_id == tracker_id)
            .order_by(EventTable.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_replicated(self, event_id: str, tracker_id: str) -> EventTable | None:
        """Marca un evento como replicado a un tracker específico"""
        event = await self.get(event_id)
        if not event:
            return None
        
        if event.replicated_to is None:
            event.replicated_to = {}
        
        event.replicated_to[tracker_id] = True
        return await self.update(event)

    async def get_pending_replication_for_tracker(
        self, target_tracker_id: str, since_timestamp: int = 0
    ) -> List[EventTable]:
        """
        Obtiene eventos que NO han sido replicados a un tracker específico.
        Si target_tracker_id es "*", devuelve eventos pendientes para cualquier tracker.
        Ordenados por timestamp para mantener causalidad.
        """
        # Obtener todos los eventos desde since_timestamp
        stmt = (
            select(EventTable)
            .where(
                EventTable.timestamp > since_timestamp,
            )
            .order_by(EventTable.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        all_events = list(result.scalars().all())
        
        # Filtrar eventos que ya fueron replicados
        if target_tracker_id == "*":
            # Para "*", devuelve eventos que aún no tienen ninguna replicación
            # O que tienen replicated_to vacío
            pending = [
                event for event in all_events
                if not event.replicated_to or not any(event.replicated_to.values())
            ]
        else:
            # Para un tracker específico, filtrar los que ya fueron replicados a ese tracker
            pending = [
                event for event in all_events
                if not (event.replicated_to and target_tracker_id in event.replicated_to)
            ]
        
        return pending
