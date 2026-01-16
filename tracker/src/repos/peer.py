from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from datetime import datetime, timedelta, UTC
from sqlalchemy import select

from src.schemas import PeerTable, TorrentTable


class PeerRepository(SQLAlchemyAsyncRepository[PeerTable]):
    model_type = PeerTable

    async def get_by_identifier(self, peer_identifier: str) -> PeerTable | None:
        """Obtiene peer por peer_identifier (client-provided peer ID)"""
        return await self.get_one_or_none(peer_identifier=peer_identifier)

    async def update_peer_activity(self, peer_id: str, **updates) -> PeerTable | None:
        """Actualiza la actividad de un peer"""
        peer = await self.get_by_identifier(peer_id)
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

    async def remove_inactive_peers(self, max_inactive_minutes: int = 30) -> int:
        """Elimina peers inactivos y retorna el número de peers eliminados"""
        cutoff_time = datetime.now(UTC) - timedelta(minutes=max_inactive_minutes)
        
        stmt = select(PeerTable).where(
            (PeerTable.last_announce < cutoff_time) | (PeerTable.last_announce == None)
        )
        result = await self.session.execute(stmt)
        inactive_peers = result.scalars().all()
        
        count = len(inactive_peers)
        for peer in inactive_peers:
            await self.delete(peer.id)
        
        await self.session.commit()
        return count

    async def upsert(
        self,
        peer_id: str,
        ip: str,
        port: int,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
        is_seed: bool = False,
    ) -> PeerTable:
        """
        Crea o actualiza un peer idempotentemente.
        Si el peer existe, actualiza sus datos.
        Si no existe, lo crea.
        """
        peer = await self.get_by_identifier(peer_id)
        if peer:
            # Actualizar peer existente
            peer.ip = ip
            peer.port = port
            peer.uploaded = uploaded
            peer.downloaded = downloaded
            peer.left = left
            peer.is_seed = is_seed
            peer.last_announce = datetime.now(UTC)
            return await self.update(peer)
        else:
            # Crear nuevo peer
            new_peer = PeerTable(
                peer_identifier=peer_id,
                ip=ip,
                port=port,
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
                is_seed=is_seed,
                last_announce=datetime.now(UTC),
            )
            return await self.add(new_peer)

    async def mark_seed(self, peer_id: str, is_seed: bool) -> PeerTable | None:
        """
        Marca un peer como seeder o leecher.
        Retorna el peer actualizado, o None si no existe.
        """
        peer = await self.get_by_identifier(peer_id)
        if not peer:
            return None
        
        peer.is_seed = is_seed
        peer.last_announce = datetime.now(UTC)
        return await self.update(peer)
