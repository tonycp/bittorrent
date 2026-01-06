from bit_lib.tools.controller import controller
from bit_lib.handlers.hander import BaseHandler
from bit_lib.handlers.crud import create, delete, update
from bit_lib.errors import NotAssociatedError, NotFoundError

from src.repos import PeerRepository, TorrentRepository, RepoContainer
from src.schemas.torrent import PeerTable
from dependency_injector.wiring import Closing, Provide
from datetime import datetime, timezone

from . import dtos

import logging


@controller("Session")
class SessionHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[RepoContainer.torrent_repo]],
        peer_repo: PeerRepository = Closing[Provide[RepoContainer.peer_repo]],
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
        logging.info(
            f"Handshake received for peer {peer_id} with protocol version {protocol_version}"
        )

        now = datetime.now(timezone.utc)
        peer = await self.peer_repo.get(peer_id)
        if not peer:
            logging.info(f"Peer {peer_id} not found, creating new peer")
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
            logging.info(
                f"Peer {peer_id} found, updating last_announce and protocol_version"
            )
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
        logging.info(f"Disconnect received for peer {peer_id} and torrent {info_hash}")
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise NotFoundError(info_hash, res_type="Torrent")

        peer = await self.peer_repo.get(peer_id)
        if not peer:
            raise NotFoundError(peer_id, res_type="Peer")

        if peer not in torrent.peers:
            raise NotAssociatedError(peer_id, info_hash, "Peer", "Torrent")

        logging.info(f"Peer {peer_id} found in torrent {info_hash}, removing")
        self.torrent_repo.remove_peer_from_torrent(info_hash, peer)
        await self.peer_repo.delete(peer)
        return {"status": "ok", "message": "Peer desconectado"}

    @update(dtos.KEEPALIVE_DATASET)
    async def keepalive(
        self,
        peer_id: str,
    ):
        logging.info(f"Received keepalive for peer {peer_id}")
        peer = await self.peer_repo.get(peer_id)
        if not peer:
            raise NotFoundError(peer_id, res_type="Peer")

        now = datetime.now(timezone.utc)
        peer.last_announce = now  # Solo actualiza el timestamp de actividad
        self.peer_repo.update_peer_activity(peer_id)

        return {
            "status": "ok",
            "message": f"Peer {peer_id} last_announce updated to {now}",
        }
