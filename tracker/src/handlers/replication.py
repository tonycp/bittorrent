from __future__ import annotations

from dependency_injector.wiring import Provide

from bit_lib.handlers import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.handlers.crud import (
    update,
)

from src.repos import (
    RepoContainer,
    PeerRepository,
    TorrentRepository,
)

from . import dtos


@controller("Replication")
class ReplicationHandler(BaseHandler):
    def __init__(
        self,
        peer_repo: PeerRepository = Provide[RepoContainer.peer_repo],
        torrent_repo: TorrentRepository = Provide[RepoContainer.torrent_repo],
    ):
        super().__init__()
        self.peer_repo = peer_repo
        self.torrent_repo = torrent_repo

    # hdl_key: "Replication:update:peer_announce"
    @update(dtos.PEER_ANNOUNCE_DATASET)
    async def peer_announce(
        self,
        ip: str,
        port: int,
        peer_id: str,
        torrent_hash: str,
        uploaded: int,
        downloaded: int,
        left: int,
    ):
        """Aplica announce directamente a repos (idempotente)"""
        await self.peer_repo.upsert(
            id=peer_id,
            ip=ip,
            port=port,
            uploaded=uploaded,
            downloaded=downloaded,
            left=left,
        )
        await self.torrent_repo.add_peer_to_torrent(
            torrent_hash=torrent_hash,
            peer_id=peer_id,
        )
        return {"status": "ok", "operation": "peer_announce"}

    # hdl_key: "Replication:update:peer_stopped"
    @update(dtos.PEER_STOPPED_DATASET)
    async def peer_stopped(
        self,
        torrent_hash: str,
        peer_id: str,
    ):
        """Remueve peer de torrent"""
        await self.torrent_repo.remove_peer_from_torrent(
            torrent_hash=torrent_hash,
            peer_id=peer_id,
        )
        return {"status": "ok", "operation": "peer_stopped"}

    # hdl_key: "Replication:update:peer_completed"
    @update(dtos.PEER_COMPLETED_DATASET)
    async def peer_completed(self, peer_id: str):
        """Marca peer como seeder"""
        await self.peer_repo.mark_seed(peer_id=peer_id, is_seed=True)
        return {"status": "ok", "operation": "peer_completed"}
