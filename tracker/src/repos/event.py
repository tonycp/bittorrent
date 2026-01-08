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
