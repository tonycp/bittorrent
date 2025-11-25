from datetime import datetime, timezone

from shared.handlers.crud import create, get
from shared.handlers.hander import BaseHandler
from shared.tools.controller import controller

from tracker.repos import PeerRepository, TorrentRepository, Repositories
from tracker.schemas.torrent import PeerTable
from dependency_injector.wiring import Closing, Provide

from sqlalchemy import text

from . import dtos


@controller("Tracker")
class TrackerHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[Repositories.torrent_repo]],
        peer_repo: PeerRepository = Closing[Provide[Repositories.peer_repo]],
    ):
        super().__init__()
        self.torrent_repo = torrent_repo
        self.peer_repo = peer_repo

    @create(dtos.ANNOUNCE_DATASET)
    async def announce(
        self,
        info_hash: str,
        peer_id: str,
        ip: str,
        port: int,
        left: int,
        event: str = None,  # Agregado para manejar eventos BT
    ):
        # Buscar el torrent
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        # Buscar el peer
        peer = await self.peer_repo.get(peer_id)
        now = datetime.now(timezone.utc)

        if not peer:
            peer = PeerTable(
                peer_id=peer_id,
                ip=ip,
                port=port,
                left=left,
                last_announce=now,
                is_seed=(event == "completed"),
            )
            await self.peer_repo.add(peer)
            await self.torrent_repo.add_peer_to_torrent(torrent.info_hash, peer)
        else:
            peer.ip = ip
            peer.port = port
            peer.left = left
            peer.last_announce = now
            if event == "completed":
                peer.is_seed = True
            if event == "stopped":
                if peer in torrent.peers:
                    torrent.peers.remove(peer)  # O marcar el peer para limpieza

        # Listar peers activos (limpia los inactivos: ejemplo, en los últimos 2 x interval)
        interval = 1800
        active_peers = [{"ip": p.ip, "port": p.port} for p in torrent.peers]

        return {
            "interval": interval,
            "peers": active_peers,
        }

    @get(dtos.PEER_LIST_DATASET)
    async def peer_list(
        self,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        active_peers = [
            {"peer_id": p.id, "ip": p.ip, "port": p.port} for p in torrent.peers
        ]

        return {"info_hash": info_hash, "peers": active_peers}

    @get(dtos.GET_PEERS_DATASET)
    async def scrape(
        self,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        now = datetime.now(timezone.utc)
        interval = 1800
        active_peers = [
            p
            for p in torrent.peers
            if p.last_announce
            and (now - p.last_announce).total_seconds() < 2 * interval
        ]
        seeders = sum(1 for p in active_peers if getattr(p, "is_seed", False))
        leechers = len(active_peers) - seeders

        return {"info_hash": info_hash, "seeders": seeders, "leechers": leechers}

    @get()
    async def prueba(self):
        session1 = self.peer_repo.session
        session2 = self.torrent_repo.session
        assert session1 == session2

        await session1.execute(text("SELECT 1"))
        return session1
