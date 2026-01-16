from __future__ import annotations

from typing import List, Dict, Any
from dependency_injector.wiring import Provide
import base64
import logging

from bit_lib.handlers import BaseHandler
from bit_lib.tools.controller import controller
from bit_lib.models import DataResponse
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

logger = logging.getLogger(__name__)


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
        try:
            # No usar transacción aquí - el handler padre ya maneja el contexto transaccional
            await self.peer_repo.upsert(
                peer_id=peer_id,
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
            logger.info(
                f"Replicated peer_announce: {peer_id} to {torrent_hash}"
            )
            return DataResponse(data={"operation": "peer_announce"})
        except Exception as e:
            logger.error(
                f"Error replicating peer_announce: {e}", exc_info=True
            )
            raise

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
        return DataResponse(data={"operation": "peer_stopped"})

    # hdl_key: "Replication:update:torrent_created"
    @update(dtos.TORRENT_CREATED_DATASET)
    async def torrent_created(
        self,
        info_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
        piece_length: int,
    ):
        """Replica creación de torrent"""
        try:
            # Verificar si ya existe
            existing = await self.torrent_repo.get(info_hash)
            if existing:
                logger.debug(f"Torrent {info_hash} ya existe, skipping")
                return DataResponse(data={"operation": "torrent_created", "status": "already_exists"})
            
            # Crear torrent
            from src.schemas.torrent import TorrentTable
            torrent = TorrentTable(
                info_hash=info_hash,
                name=file_name,
                size=file_size,
                chunks=total_chunks,
                piece_length=piece_length,
            )
            
            await self.torrent_repo.add(torrent)
            logger.info(f"Replicated torrent_created: {info_hash} - {file_name}")
            
            return DataResponse(data={"operation": "torrent_created"})
        except Exception as e:
            logger.error(f"Error replicating torrent_created: {e}", exc_info=True)
            raise

    # hdl_key: "Replication:update:peer_completed"
    @update(dtos.PEER_COMPLETED_DATASET)
    async def peer_completed(self, peer_id: str):
        """Marca peer como seeder"""
        try:
            peer = await self.peer_repo.mark_seed(peer_id=peer_id, is_seed=True)
            if peer:
                logger.info(f"Replicated peer_completed: {peer_id} marked as seeder")
                return DataResponse(data={"operation": "peer_completed"})
            else:
                logger.warning(f"Peer not found for peer_completed: {peer_id}")
                raise ValueError(f"Peer {peer_id} not found")
        except Exception as e:
            logger.error(
                f"Error replicating peer_completed: {e}", exc_info=True
            )
            raise

    # hdl_key: "Replication:update:replicate_events"
    @update(dtos.REPLICATE_EVENTS_DATASET)
    async def replicate_events(
        self,
        source_tracker_id: str,
        events: List[Dict[str, Any]],
    ):
        """
        Recibe lote de eventos de otro tracker y los aplica directamente.
        
        Usa vector clocks para detectar inconsistencias y aplicar "último escritor gana".
        Esto permite reconciliar particiones de red cuando se reconectan.
        """
        import logging
        from src.models import EventLog
        from src.schemas.torrent import TorrentTable
        from bit_lib.context import VectorClock
        
        logging.info(f"Received {len(events)} events from {source_tracker_id}")
        
        applied = 0
        skipped = 0
        errors = []

        for event in events:
            try:
                # Los eventos pueden venir como dict o como EventLog (Pydantic)
                if isinstance(event, dict):
                    operation = event.get("operation")
                    data = event.get("data", {})
                    event_vc_dict = event.get("vector_clock", {})
                    event_timestamp = event.get("timestamp", 0)
                else:
                    # Es un objeto EventLog
                    operation = event.operation
                    data = event.data
                    event_vc_dict = event.vector_clock if hasattr(event, "vector_clock") else {}
                    event_timestamp = event.timestamp if hasattr(event, "timestamp") else 0

                if not operation:
                    logging.warning(f"Event without operation")
                    errors.append({"event": "missing_operation", "error": "No operation field"})
                    continue

                # Crear VectorClock del evento
                event_vc = VectorClock(clock=event_vc_dict if isinstance(event_vc_dict, dict) else {})
                
                # Obtener VectorClock local actual para este tracker
                # (Esto permite detectar eventos antiguos o duplicados)
                local_vc = await self._get_local_vector_clock()
                
                # Verificar causalidad: ¿Deberíamos aplicar este evento?
                # Si event_vc <= local_vc, el evento ya fue aplicado o está desactualizado
                if event_vc <= local_vc and event_timestamp <= local_vc.get(source_tracker_id):
                    logging.debug(
                        f"Skipping event {operation} from {source_tracker_id}: "
                        f"already applied (event_ts={event_timestamp}, local_ts={local_vc.get(source_tracker_id)})"
                    )
                    skipped += 1
                    continue

                logging.debug(f"Applying operation: {operation} with data: {data}")

                # Aplicar directamente a repos (sin llamar a métodos que usan @update)
                if operation == "peer_announce":
                    # Aplicar peer announce directamente
                    await self.peer_repo.upsert(
                        peer_id=data["peer_id"],
                        ip=data["ip"],
                        port=data["port"],
                        uploaded=data["uploaded"],
                        downloaded=data["downloaded"],
                        left=data["left"],
                    )
                    await self.torrent_repo.add_peer_to_torrent(
                        info_hash=data["torrent_hash"],
                        peer_identifier=data["peer_id"],
                    )
                    logging.info(f"Replicated peer_announce: {data['peer_id']} to {data['torrent_hash']}")
                    
                elif operation == "peer_stopped":
                    # Remover peer del torrent
                    await self.torrent_repo.remove_peer_from_torrent(
                        info_hash=data["torrent_hash"],
                        peer_identifier=data["peer_id"],
                    )
                    logging.info(f"Replicated peer_stopped: {data['peer_id']} from {data['torrent_hash']}")
                    
                elif operation == "torrent_created":
                    # Verificar si ya existe
                    existing = await self.torrent_repo.get(data["info_hash"])
                    if existing:
                        logging.debug(f"Torrent {data['info_hash']} already exists, skipping")
                    else:
                        # Crear torrent directamente
                        torrent = TorrentTable(
                            info_hash=data["info_hash"],
                            name=data["file_name"],
                            size=data["file_size"],
                            chunks=data["total_chunks"],
                            piece_length=data["piece_length"],
                        )
                        await self.torrent_repo.add(torrent)
                        logging.info(f"Replicated torrent_created: {data['info_hash']}")
                        
                elif operation == "peer_completed":
                    # Marcar peer como seeder
                    await self.peer_repo.mark_seed(peer_id=data["peer_id"], is_seed=True)
                    logging.info(f"Replicated peer_completed: {data['peer_id']}")
                    
                else:
                    # Operación desconocida
                    logging.warning(f"Unknown replication operation: {operation}")
                    errors.append(
                        {
                            "event": str(event),
                            "error": f"Unknown operation: {operation}",
                        }
                    )
                    continue

                applied += 1

            except Exception as e:
                logging.error(f"Error applying replicated event: {e}", exc_info=True)
                errors.append({"event": str(event), "error": str(e)})

        # Flush para asegurar que los cambios se persisten
        try:
            await self.torrent_repo.session.flush()
            logging.debug(f"Flushed session after applying {applied} events")
        except Exception as e:
            logging.warning(f"Error flushing session: {e}")

        logging.info(
            f"Applied {applied}/{len(events)} events from {source_tracker_id}, "
            f"skipped {skipped}, errors: {len(errors)}"
        )
        
        return DataResponse(
            data={
                "applied": applied,
                "skipped": skipped,
                "errors": errors,
                "source_tracker": source_tracker_id,
            }
        )
    
    async def _get_local_vector_clock(self):
        """Obtiene el VectorClock local actual desde el último evento"""
        from bit_lib.context import VectorClock
        import os
        
        tracker_id = os.getenv("TRACKER_ID", "tracker-unknown")
        
        # Obtener último evento local
        latest_event = await self.event_repo.get_latest_by_tracker(tracker_id)
        
        if latest_event and hasattr(latest_event, "vector_clock"):
            return VectorClock(clock=latest_event.vector_clock)
        else:
            # Si no hay eventos, crear VC inicial
            return VectorClock(clock={tracker_id: 0})

    # hdl_key: "Replication:create:heartbeat"
    @create(dtos.REPLICATION_HEARTBEAT_DATASET)
    async def heartbeat(
        self,
        tracker_id: str,
        last_timestamp: int,
        event_count: int,
    ):
        """Recibe heartbeat de otro tracker para confirmar que está vivo"""
        return DataResponse(
            data={
                "status": "alive",
                "tracker_id": tracker_id,
                "acknowledged_timestamp": last_timestamp,
            }
        )

    # hdl_key: "Replication:update:replicate_snapshot_chunk"
    @update(dtos.REPLICATE_SNAPSHOT_CHUNK_DATASET)
    async def replicate_snapshot_chunk(
        self,
        source_tracker_id: str,
        snapshot_id: str,
        block_index: int,
        total_size: int,
        chunk_data: str,  # base64 encoded
    ):
        """Recibe chunk de snapshot (parte de snapshot binario grande)"""
        try:
            # Decodificar base64
            decoded_data = base64.b64decode(chunk_data.encode("utf-8"))

            logger.debug(
                f"Recibido chunk {block_index} de snapshot {snapshot_id} "
                f"({len(decoded_data)} bytes de {total_size})"
            )

            # Aquí se llama a ReplicationService._handle_binary con los datos
            # Pero como esto es en el handler, necesitamos una forma de pasar esto
            # a ReplicationService. Por ahora, loguear y asumir que el service
            # se encargará de reconstituir cuando complete.

            return DataResponse(
                data={
                    "status": "chunk_received",
                    "snapshot_id": snapshot_id,
                    "block_index": block_index,
                }
            )
        except Exception as e:
            logger.error(f"Error procesando chunk de snapshot: {e}")
            return DataResponse(
                data={
                    "status": "error",
                    "error": str(e),
                }
            )

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
        from bit_lib.context import VectorClock

        vc = (
            last_event.vector_clock
            if last_event
            else VectorClock(clock={tracker_id: 0})
        )

        return DataResponse(
            data={
                "source_tracker_id": tracker_id,
                "vector_clock": vc.to_dict() if hasattr(vc, "to_dict") else vc,
                "torrents": [t.model_dump() for t in torrents],
                "peers": [p.model_dump() for p in peers],
            }
        )

    # hdl_key: "Replication:update:replicate_snapshot"
    @update(dtos.REPLICATE_SNAPSHOT_DATASET)
    async def replicate_snapshot(
        self,
        source_tracker_id: str,
        vector_clock: Dict[str, int],
        torrents: List,  # List[Torrent] after validation
        peers: List,  # List[Peer] after validation
    ):
        """Aplica snapshot inicial de otro tracker (para inicializar tracker nuevo)"""
        # Aplicar peers
        for peer in peers:
            peer_data = peer.model_dump() if hasattr(peer, "model_dump") else peer
            await self.peer_repo.upsert(**peer_data)

        # Aplicar torrents
        for torrent in torrents:
            torrent_data = (
                torrent.model_dump() if hasattr(torrent, "model_dump") else torrent
            )
            # TODO: implementar create/upsert en torrent_repo
            pass

        return DataResponse(
            data={
                "status": "snapshot_applied",
                "source_tracker": source_tracker_id,
                "torrents_count": len(torrents),
                "peers_count": len(peers),
                "vector_clock": vector_clock,
            }
        )
