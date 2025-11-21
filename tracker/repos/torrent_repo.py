from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from tracker.schemas import TorrentTable, PeerTable


class TorrentRepository(SQLAlchemyAsyncRepository[TorrentTable]):
    model_type = TorrentTable

    async def get(self, info_hash: str) -> TorrentTable | None:
        """Obtiene torrent por info_hash con peers cargados"""
        stmt = (
            select(TorrentTable)
            .options(selectinload(TorrentTable.peers))
            .where(TorrentTable.info_hash == info_hash)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_peer_to_torrent(self, info_hash: str, peer: PeerTable) -> bool:
        """Agrega un peer a un torrent"""
        torrent = await self.get(info_hash)
        if not torrent:
            return False

        if peer not in torrent.peers:
            torrent.peers.append(peer)
            await self.update(torrent)
        return True

    async def remove_peer_from_torrent(self, info_hash: str, peer_id: str) -> bool:
        """Remueve un peer de un torrent"""
        torrent = await self.get(info_hash)
        if not torrent:
            return False

        peer_to_remove = next((p for p in torrent.peers if p.id == peer_id), None)
        if peer_to_remove:
            torrent.peers.remove(peer_to_remove)
            await self.update(torrent)
            return True
        return False

    async def get_torrent_stats(self, info_hash: str) -> dict:
        """Obtiene estadísticas del torrent"""
        torrent = await self.get(info_hash)
        if not torrent:
            return {}

        seeders = sum(1 for peer in torrent.peers if peer.is_seed)
        leechers = len(torrent.peers) - seeders

        return {
            "info_hash": info_hash,
            "total_peers": len(torrent.peers),
            "seeders": seeders,
            "leechers": leechers,
        }
