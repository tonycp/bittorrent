from datetime import datetime, timezone

from bit_lib.handlers.crud import create, get
from bit_lib.handlers.hander import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.models import DataResponse

from src.repos import PeerRepository, TorrentRepository, RepoContainer
from src.schemas.torrent import PeerTable
from dependency_injector.wiring import Closing, Provide

from sqlalchemy import text

from . import dtos
import logging

logger = logging.getLogger(__name__)


@controller("Bit")
class BitHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[RepoContainer.torrent_repo]],
        peer_repo: PeerRepository = Closing[Provide[RepoContainer.peer_repo]],
    ):
        super().__init__()
        self.torrent_repo = torrent_repo
        self.peer_repo = peer_repo
        self.request_handler = None  # Se asigna desde TrackerService

    def _resolve_tracker_id(self) -> str:
        import os

        return (
            os.getenv("SERVICES__TRACKER_ID")
            or os.getenv("TRACKER_ID")
            or "tracker-unknown"
        )

    @create(dtos.ANNOUNCE_DATASET)
    async def announce(
        self,
        info_hash: str,
        peer_id: str,
        ip: str,
        port: int,
        left: int,
        event: str = None,
    ):
        try:
            now = datetime.now(timezone.utc)

            torrent = await self.torrent_repo.get(info_hash)
            if not torrent:
                raise ValueError("Torrent no encontrado")

            peer = await self.peer_repo.get_by_identifier(peer_id)
            is_seeder = left == 0 or event == "completed"

            if not peer:
                peer = PeerTable(
                    peer_identifier=peer_id,
                    ip=ip,
                    port=port,
                    left=left,
                    last_announce=now,
                    is_seed=is_seeder,
                )
                await self.peer_repo.add(peer)
                # Solo vinculamos si no es un evento de parada
                if event != "stopped":
                    await self.torrent_repo.add_peer_to_torrent(info_hash, peer_id)
            else:
                # Actualizar datos del peer existente
                peer.ip, peer.port, peer.left = ip, port, left
                peer.last_announce = now
                peer.is_seed = is_seeder
                await self.peer_repo.update(peer)

            if event == "stopped":
                await self.torrent_repo.remove_peer_from_torrent(info_hash, peer_id)
                
                # Generar evento para replicación
                await self._create_event(
                    operation="peer_stopped",
                    data={
                        "torrent_hash": info_hash,
                        "peer_id": peer_id,
                    }
                )
                
                # Si se detiene, devolvemos una lista vacía o mínima rápidamente
                return DataResponse(data={"interval": 1800, "peers": []})

            if event == "started" or not event:
                # Asegurar que esté vinculado (por si el registro se perdió o es nuevo)
                await self.torrent_repo.add_peer_to_torrent(info_hash, peer_id)
                
                # Generar evento para replicación
                await self._create_event(
                    operation="peer_announce",
                    data={
                        "torrent_hash": info_hash,
                        "peer_id": peer_id,
                        "ip": ip,
                        "port": port,
                        "left": left,
                        "uploaded": 0,
                        "downloaded": 0,
                    }
                )

            # IMPORTANTE: Filtrar para no enviarse a sí mismo (peer_id)
            # Y opcionalmente limitar la cantidad (ej. top 50)
            peers_list = await self.torrent_repo.get_active_peers(
                info_hash, exclude_peer_id=peer_id
            )

            active_peers = [{"ip": p.ip, "port": p.port} for p in peers_list]

            return DataResponse(
                data={
                    "interval": 1800,  # 30 min estándar
                    "peers": active_peers,
                }
            )
        except Exception as e:
            logger.error(f"Announce error: {e}", exc_info=True)
            raise

    async def _create_event(self, operation: str, data: dict):
        """Helper para crear eventos que se replicarán entre trackers via callback"""
        from bit_lib.models import Request
        
        if not self.request_handler:
            logger.warning("No request_handler available, skipping event creation")
            return
        
        tracker_id = self._resolve_tracker_id()
        
        try:
            # Crear request para EventHandler
            req = Request(
                controller="Event",
                command="create",
                func="create_event",
                args={
                    "tracker_id": tracker_id,
                    "operation": operation,
                    "data": data,
                },
            )
            # Llamar directamente al handler del servidor principal
            result = await self.request_handler(req)
            if getattr(result, "type", None) == "error":
                logger.warning(f"[{tracker_id}] Error response creando evento {operation}: {result}")
            logger.debug(f"[{tracker_id}] Evento creado: {operation}")
        except Exception as e:
            logger.warning(f"[{tracker_id}] Error creando evento: {e}")

    @get(dtos.PEER_LIST_DATASET)
    async def peer_list(
        self,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        now = datetime.now(timezone.utc)
        interval = 1800  # 30 minutos

        # 2. Filtrar solo los que están realmente activos (Grace period de 2x intervalo)
        active_peers = []
        for p in torrent.peers:
            is_active = (
                p.last_announce
                and (now - p.last_announce).total_seconds() < 2 * interval
            )

            if is_active:
                active_peers.append(
                    {
                        "peer_id": p.peer_identifier,  # El ID de 20 bytes de BitTorrent
                        "ip": p.ip,
                        "port": p.port,
                        "is_seed": p.is_seed,
                        "last_seen": p.last_announce.isoformat(),
                    }
                )

        return DataResponse(
            data={
                "info_hash": info_hash,
                "total_active": len(active_peers),
                "peers": active_peers,
            }
        )

    @get(dtos.GET_PEERS_DATASET)
    async def scrape(
        self,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        now = datetime.now(timezone.utc)
        # Definimos un margen de gracia para considerar a un peer "muerto"
        # Si el intervalo es 1800s, un peer que no ha hablado en 3600s está fuera.
        EXPIRATION_MARGIN = 3600

        active_peers = [
            p
            for p in torrent.peers
            if p.last_announce
            and (now - p.last_announce).total_seconds() < EXPIRATION_MARGIN
        ]

        seeders = sum(1 for p in active_peers if p.is_seed or p.left == 0)
        leechers = len(active_peers) - seeders

        return DataResponse(
            data={
                "info_hash": info_hash,
                "incomplete": leechers,
                "complete": seeders,
            }
        )

    @get()
    async def prueba(self):
        session1 = self.peer_repo.session
        session2 = self.torrent_repo.session
        assert session1 == session2

        await session1.execute(text("SELECT 1"))
        return session1
