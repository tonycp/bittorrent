from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from datetime import datetime, timedelta, UTC
from sqlalchemy import select

from tracker.schemas import PeerTable, TorrentTable


class PeerRepository(SQLAlchemyAsyncRepository[PeerTable]):
    model_type = PeerTable

    async def get(self, peer_id: str) -> PeerTable | None:
        """Obtiene peer por peer_id"""
        return await self.get_one_or_none(peer_id=peer_id)

    async def update_peer_activity(self, peer_id: str, **updates) -> PeerTable | None:
        """Actualiza la actividad de un peer"""
        peer = await self.get(peer_id)
        if not peer:
            return None

        for field, value in updates.items():
            if hasattr(peer, field):
                setattr(peer, field, value)

        peer.last_announce = datetime.now(UTC)
        return await self.update(peer)

    async def get_active_peers(self, max_inactive_minutes: int = 30):
        """Obtiene peers activos"""
        cutoff_time = datetime.now(UTC) - timedelta(minutes=max_inactive_minutes)

        stmt = select(PeerTable).where(PeerTable.last_announce >= cutoff_time)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_peers_by_torrent(self, info_hash: str):
        """Obtiene peers de un torrent específico"""
        stmt = (
            select(PeerTable)
            .join(PeerTable.torrents)
            .where(TorrentTable.info_hash == info_hash)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
