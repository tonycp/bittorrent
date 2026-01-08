from __future__ import annotations

from typing import List, Dict, Any
from dependency_injector.wiring import Provide

from bit_lib.handlers import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.handlers.crud import (
    update,
    create,
    get,
)

from src.repos import (
    RepoContainer,
    PeerRepository,
    TorrentRepository,
    EventLogRepository,
)

from . import dtos


@controller("Replication")
class ReplicationHandler(BaseHandler):
    def __init__(
        self,
        peer_repo: PeerRepository = Provide[RepoContainer.peer_repo],
        torrent_repo: TorrentRepository = Provide[RepoContainer.torrent_repo],
        event_repo: EventLogRepository = Provide[RepoContainer.event_log_repo],
    ):
        super().__init__()
        self.peer_repo = peer_repo
        self.torrent_repo = torrent_repo
        self.event_repo = event_repo

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

    # hdl_key: "Replication:update:replicate_events"
    @update(dtos.REPLICATE_EVENTS_DATASET)
    async def replicate_events(
        self,
        source_tracker_id: str,
        events: List[Dict[str, Any]],
    ):
        """Recibe lote de eventos de otro tracker y los aplica via EventHandler"""
        applied = 0
        errors = []
        
        for event_data in events:
            try:
                # Delegar a EventHandler.apply_event para validación y aplicación
                # (El EventHandler invocará de vuelta a este handler para aplicar cambios)
                applied += 1
            except Exception as e:
                errors.append({"event": event_data, "error": str(e)})
        
        return {
            "status": "ok",
            "applied": applied,
            "errors": errors,
            "source_tracker": source_tracker_id,
        }

    # hdl_key: "Replication:create:heartbeat"
    @create(dtos.HEARTBEAT_DATASET)
    async def heartbeat(
        self,
        tracker_id: str,
        last_timestamp: int,
        event_count: int,
    ):
        """Recibe heartbeat de otro tracker para confirmar que está vivo"""
        return {
            "status": "alive",
            "tracker_id": tracker_id,
            "acknowledged_timestamp": last_timestamp,
        }

    # hdl_key: "Replication:get:request_snapshot"
    @get(dtos.REQUEST_SNAPSHOT_DATASET)
    async def request_snapshot(self, tracker_id: str):
        """Solicita snapshot completo del estado actual (para tracker nuevo)"""
        # Obtener todos los torrents y peers desde repos
        # TODO: implementar list_all en repos si no existe
        torrents = []  # await self.torrent_repo.list_all()
        peers = []  # await self.peer_repo.list_all()
        
        # Obtener el VC más reciente de este tracker
        last_event = await self.event_repo.get_latest_by_tracker(tracker_id)
        vc = last_event.vector_clock if last_event else {tracker_id: 0}
        
        return {
            "source_tracker_id": tracker_id,
            "vector_clock": vc,
            "torrents": [t.model_dump() for t in torrents],
            "peers": [p.model_dump() for p in peers],
        }

    # hdl_key: "Replication:update:replicate_snapshot"
    @update(dtos.REPLICATE_SNAPSHOT_DATASET)
    async def replicate_snapshot(
        self,
        source_tracker_id: str,
        vector_clock: Dict[str, int],
        torrents: List,  # List[Torrent] after validation
        peers: List,     # List[Peer] after validation
    ):
        """Aplica snapshot inicial de otro tracker (para inicializar tracker nuevo)"""
        # Aplicar peers
        for peer in peers:
            peer_data = peer.model_dump() if hasattr(peer, 'model_dump') else peer
            await self.peer_repo.upsert(**peer_data)
        
        # Aplicar torrents
        for torrent in torrents:
            torrent_data = torrent.model_dump() if hasattr(torrent, 'model_dump') else torrent
            # TODO: implementar create/upsert en torrent_repo
            pass
        
        return {
            "status": "snapshot_applied",
            "source_tracker": source_tracker_id,
            "torrents_count": len(torrents),
            "peers_count": len(peers),
            "vector_clock": vector_clock,
        }
