from datetime import datetime, timezone

from shared.handlers.crud import create, delete, update
from shared.handlers.hander import BaseHandler
from shared.proto.message import DataSerialize

from tracker.repos import PeerRepository, TorrentRepository
from shared.tools.controller import controller
from tracker.schemas.torrent import PeerTable

from . import dtos


@controller("Session")
class SessionHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository,
        peer_repo: PeerRepository,
    ):
        super().__init__()
        self.torrent_repo = torrent_repo
        self.peer_repo = peer_repo

    @create(dtos.HANDSHAKE_DATASET)
    async def handshake(
        self,
        peer_id: str,
        protocol_version: str,
    ):
        if protocol_version != DataSerialize.VERSION:
            raise ValueError("Versión de protocolo no soportada")

        now = datetime.now(timezone.utc)
        peer = await self.peer_repo.get(peer_id)
        if not peer:
            peer = PeerTable(
                peer_id=peer_id,
                ip="0.0.0.0",
                port=0,
                left=0,
                last_announce=now,
                is_seed=False,
                protocol_version=protocol_version,
            )
            await self.peer_repo.add(peer)
        else:
            peer.protocol_version = protocol_version
            peer.last_announce = now

        return {
            "status": "ok",
            "message": "Handshake exitoso",
            "protocol_version": protocol_version,
        }

    @delete(dtos.DISCONNECT_DATASET)
    async def disconnect(
        self,
        peer_id: str,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        peer = await self.peer_repo.get(peer_id)
        if not peer:
            raise ValueError("Peer no encontrado")

        # Elimina el peer de la lista del torrent
        if peer in torrent.peers:
            self.torrent_repo.remove_peer_from_torrent(info_hash, peer)
            await self.peer_repo.delete(peer)
            return {"status": "ok", "message": "Peer desconectado"}
        else:
            return {"status": "not_found", "message": "Peer no asociado al torrent"}

    @update(dtos.KEEPALIVE_DATASET)
    async def keepalive(
        self,
        peer_id: str,
    ):
        peer = await self.peer_repo.get(peer_id)
        if not peer:
            raise ValueError("Peer no encontrado")

        now = datetime.now(timezone.utc)
        peer.last_announce = now  # Solo actualiza el timestamp de actividad
        self.peer_repo.update_peer_activity(peer_id)

        return {"status": "ok", "message": "Seguimiento de actividad actualizado"}
