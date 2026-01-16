from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from sqlalchemy.orm import selectinload
from sqlalchemy import select, insert, delete, and_

from src.schemas import TorrentTable, PeerTable, torrent_peers

import logging

logger = logging.getLogger(__name__)


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

    async def is_peer_in_torrent(self, info_hash: str, peer_identifier: str) -> bool:
        """Verifica si un peer está asociado a un torrent"""

        torrent = await self.get(info_hash)
        if not torrent:
            return False

        peer_result = await self.session.execute(
            select(PeerTable).where(PeerTable.peer_identifier == peer_identifier)
        )
        peer_obj = peer_result.scalar_one_or_none()
        if not peer_obj:
            return False

        # Verificar la relación en la tabla junction
        stmt = select(torrent_peers).where(
            and_(
                torrent_peers.c.torrent_id == torrent.id,
                torrent_peers.c.peer_id == peer_obj.id,
            )
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def add_peer_to_torrent(self, info_hash: str, peer_identifier: str) -> bool:
        """Agrega un peer a un torrent usando su peer_identifier"""
        from src.schemas.torrent import torrent_peers
        import logging
        from sqlalchemy import and_

        logger = logging.getLogger(__name__)

        # Obtener torrent y peer
        torrent = await self.get(info_hash)
        if not torrent:
            logger.error(f"Torrent {info_hash} not found")
            return False

        peer_result = await self.session.execute(
            select(PeerTable).where(PeerTable.peer_identifier == peer_identifier)
        )
        peer = peer_result.scalar_one_or_none()
        if not peer:
            logger.error(f"Peer {peer_identifier} not found")
            return False

        # Verificar si ya existe la relación
        check_stmt = select(torrent_peers).where(
            and_(
                torrent_peers.c.torrent_id == torrent.id,
                torrent_peers.c.peer_id == peer.id,
            )
        )
        existing = await self.session.execute(check_stmt)
        if existing.first():
            logger.info(f"Relationship already exists: torrent_id={torrent.id}, peer_id={peer.id}")
            return True

        logger.info(
            f"Inserting relationship: torrent_id={torrent.id}, peer_id={peer.id}"
        )

        # Insertar relación directamente en la tabla junction
        stmt = insert(torrent_peers).values(
            torrent_id=torrent.id,
            peer_id=peer.id,
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        logger.info(f"Inserted: {result.rowcount} rows")
        return result.rowcount > 0

    async def remove_peer_from_torrent(
        self, info_hash: str, peer_identifier: str
    ) -> bool:
        """Remueve un peer de un torrent"""
        from src.schemas.torrent import torrent_peers

        # Obtener el torrent
        torrent = await self.get(info_hash)
        if not torrent:
            return False

        # Obtener el peer por su identificador
        peer_result = await self.session.execute(
            select(PeerTable).where(PeerTable.peer_identifier == peer_identifier)
        )
        peer = peer_result.scalar_one_or_none()
        if not peer:
            return False

        # Eliminar la relación
        stmt = delete(torrent_peers).where(
            and_(
                torrent_peers.c.torrent_id == torrent.id,
                torrent_peers.c.peer_id == peer.id,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

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

    async def remove_orphaned_torrents(self) -> int:
        """Elimina torrents sin peers asociados y retorna el número eliminado"""
        stmt = select(TorrentTable).options(selectinload(TorrentTable.peers))
        result = await self.session.execute(stmt)
        all_torrents = result.scalars().all()
        
        count = 0
        for torrent in all_torrents:
            if not torrent.peers or len(torrent.peers) == 0:
                await self.delete(torrent.id)
                count += 1
        
        await self.session.commit()
        return count

    async def get_active_peers(self, info_hash: str, exclude_peer_id: str = None) -> list[PeerTable]:
        """Obtiene los peers activos de un torrent, opcionalmente excluyendo uno"""
        from datetime import datetime, timezone, timedelta
        
        torrent = await self.get(info_hash)
        if not torrent:
            return []

        # Filtrar peers activos (que hayan hecho announce en los últimos 1 hora)
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        active_peers = [
            p
            for p in torrent.peers
            if p.last_announce and p.last_announce > hour_ago
            and (not exclude_peer_id or p.peer_identifier != exclude_peer_id)
        ]

        return active_peers