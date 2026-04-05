from __future__ import annotations

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import select

from src.schemas import ReplicaAssignmentTable


class ReplicaAssignmentRepository(SQLAlchemyAsyncRepository[ReplicaAssignmentTable]):
    model_type = ReplicaAssignmentTable

    async def get_by_torrent_hash(self, torrent_hash: str) -> ReplicaAssignmentTable | None:
        stmt = select(ReplicaAssignmentTable).where(
            ReplicaAssignmentTable.torrent_hash == torrent_hash
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_replica_set(
        self, torrent_hash: str, replica_set: list[str]
    ) -> ReplicaAssignmentTable:
        normalized = [tracker_id for tracker_id in replica_set if isinstance(tracker_id, str)]

        existing = await self.get_by_torrent_hash(torrent_hash)
        if existing:
            existing.replica_set = normalized
            await self.session.flush()
            return await self.update(existing)

        entity = ReplicaAssignmentTable(
            torrent_hash=torrent_hash,
            replica_set=normalized,
        )
        return await self.add(entity)
