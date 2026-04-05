from __future__ import annotations

from typing import List, Dict, Any
from dependency_injector.wiring import Provide
import base64
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
        self._snapshot_chunks: Dict[str, Dict[str, Any]] = {}
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
        from src.schemas.torrent import TorrentTable
        from bit_lib.context import VectorClock
        
        logging.info(f"Received {len(events)} events from {source_tracker_id}")
        
        applied = 0
        skipped = 0
        errors = []
        applied_event_ids: list[str] = []

        for event in events:
            try:
                # Los eventos pueden venir como dict o como EventLog (Pydantic)
                if isinstance(event, dict):
                    event_id = str(event.get("id")) if event.get("id") is not None else None
                    operation = event.get("operation")
                    data = event.get("data", {})
                    event_vc_dict = event.get("vector_clock", {})
                    event_timestamp = event.get("timestamp", 0)
                else:
                    event_id = str(getattr(event, "id", "")) if getattr(event, "id", None) is not None else None
                    # Es un objeto EventLog
                    operation = event.operation
                    data = event.data
                    event_vc_dict = event.vector_clock if hasattr(event, "vector_clock") else {}
                    event_timestamp = event.timestamp if hasattr(event, "timestamp") else 0

                if not operation:
                    logging.warning("Event without operation")
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
                if event_id:
                    applied_event_ids.append(event_id)

                # Persistir por evento para evitar perder progreso si uno falla
                await self.torrent_repo.session.flush()
                await self.torrent_repo.session.commit()

            except Exception as e:
                logging.error(f"Error applying replicated event: {e}", exc_info=True)
                try:
                    await self.torrent_repo.session.rollback()
                except Exception:
                    pass
                errors.append({"event": str(event), "error": str(e)})

        logging.info(
            f"Applied {applied}/{len(events)} events from {source_tracker_id}, "
            f"skipped {skipped}, errors: {len(errors)}"
        )
        
        return DataResponse(
            data={
                "applied": applied,
                "applied_event_ids": applied_event_ids,
                "skipped": skipped,
                "errors": errors,
                "source_tracker": source_tracker_id,
            }
        )
    
    async def _get_local_vector_clock(self):
        """Obtiene el VectorClock local actual desde el último evento"""
        from bit_lib.context import VectorClock
        import os

        tracker_id = (
            os.getenv("SERVICES__TRACKER_ID")
            or os.getenv("TRACKER_ID")
            or "tracker-unknown"
        )
        
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
        chunk_data: str,
    ):
        """Recibe chunks base64, recompone snapshot y ejecuta replicate_snapshot."""
        try:
            decoded_data = base64.b64decode(chunk_data.encode("utf-8"))

            state = self._snapshot_chunks.setdefault(
                snapshot_id,
                {
                    "source_tracker_id": source_tracker_id,
                    "total_size": total_size,
                    "chunks": {},
                },
            )
            state["chunks"][block_index] = decoded_data

            received_size = sum(len(chunk) for chunk in state["chunks"].values())
            logger.debug(
                f"Recibido chunk {block_index} de snapshot {snapshot_id} "
                f"({received_size}/{total_size} bytes)"
            )

            if received_size < total_size:
                return DataResponse(
                    data={
                        "status": "chunk_received",
                        "snapshot_id": snapshot_id,
                        "block_index": block_index,
                    }
                )

            ordered_blocks = [
                state["chunks"][idx] for idx in sorted(state["chunks"].keys())
            ]
            snapshot_bytes = b"".join(ordered_blocks)[:total_size]
            snapshot_data = json.loads(snapshot_bytes.decode("utf-8"))

            await self.replicate_snapshot(
                source_tracker_id=snapshot_data["source_tracker_id"],
                vector_clock=snapshot_data["vector_clock"],
                torrents=snapshot_data.get("torrents", []),
                peers=snapshot_data.get("peers", []),
            )

            self._snapshot_chunks.pop(snapshot_id, None)

            return DataResponse(
                data={
                    "status": "snapshot_applied",
                    "snapshot_id": snapshot_id,
                    "total_chunks": len(ordered_blocks),
                }
            )
        except Exception as e:
            logger.error(f"Error procesando chunk de snapshot: {e}", exc_info=True)
            self._snapshot_chunks.pop(snapshot_id, None)
            return DataResponse(
                data={
                    "status": "error",
                    "error": str(e),
                }
            )

    # hdl_key: "Replication:get:request_snapshot"
    @get(dtos.REQUEST_SNAPSHOT_DATASET)
    async def request_snapshot(self, tracker_id: str):
        """Solicita snapshot completo del estado actual (para tracker nuevo)."""
        from src.schemas.torrent import TorrentTable, PeerTable
        from bit_lib.context import VectorClock

        torrent_stmt = select(TorrentTable).options(selectinload(TorrentTable.peers))
        torrent_result = await self.torrent_repo.session.execute(torrent_stmt)
        torrent_rows = torrent_result.scalars().all()

        peer_stmt = select(PeerTable)
        peer_result = await self.peer_repo.session.execute(peer_stmt)
        peer_rows = peer_result.scalars().all()

        last_event = await self.event_repo.get_latest_by_tracker(tracker_id)
        vc = last_event.vector_clock if last_event else VectorClock(clock={tracker_id: 0}).to_dict()

        torrents = [
            {
                "info_hash": torrent.info_hash,
                "name": torrent.name,
                "size": torrent.size,
                "chunks": torrent.chunks,
                "piece_length": torrent.piece_length,
                "peer_ids": [peer.peer_identifier for peer in (torrent.peers or [])],
            }
            for torrent in torrent_rows
        ]

        peers = [
            {
                "peer_identifier": peer.peer_identifier,
                "ip": peer.ip,
                "port": peer.port,
                "uploaded": peer.uploaded,
                "downloaded": peer.downloaded,
                "left": peer.left,
                "is_seed": peer.is_seed,
                "last_announce": peer.last_announce,
                "status": peer.status,
                "protocol_version": peer.protocol_version,
            }
            for peer in peer_rows
        ]

        return DataResponse(
            data={
                "source_tracker_id": tracker_id,
                "vector_clock": vc,
                "torrents": torrents,
                "peers": peers,
            }
        )

    # hdl_key: "Replication:update:replicate_snapshot"
    @update(dtos.REPLICATE_SNAPSHOT_DATASET)
    async def replicate_snapshot(
        self,
        source_tracker_id: str,
        vector_clock: Dict[str, int],
        torrents: List,
        peers: List,
    ):
        """Aplica snapshot inicial de otro tracker (torrents + peers + relaciones)."""
        from src.schemas.torrent import TorrentTable

        applied_torrents = 0
        applied_peers = 0
        linked_relations = 0

        # 1) Upsert torrents base
        for torrent in torrents:
            torrent_data = torrent.model_dump() if hasattr(torrent, "model_dump") else torrent
            info_hash = torrent_data.get("info_hash") or torrent_data.get("hash")
            if not info_hash:
                continue

            existing = await self.torrent_repo.get(info_hash)
            if not existing:
                await self.torrent_repo.add(
                    TorrentTable(
                        info_hash=info_hash,
                        name=torrent_data.get("name"),
                        size=torrent_data.get("size", 0),
                        chunks=torrent_data.get("chunks", 0),
                        piece_length=torrent_data.get("piece_length", 262144),
                    )
                )
                applied_torrents += 1

        # 2) Upsert peers
        for peer in peers:
            peer_data = peer.model_dump() if hasattr(peer, "model_dump") else peer
            peer_identifier = peer_data.get("peer_identifier") or peer_data.get("peer_id")
            if not peer_identifier:
                continue

            await self.peer_repo.upsert(
                peer_id=peer_identifier,
                ip=peer_data.get("ip", "0.0.0.0"),
                port=peer_data.get("port", 0),
                uploaded=peer_data.get("uploaded", 0),
                downloaded=peer_data.get("downloaded", 0),
                left=peer_data.get("left", 0),
                is_seed=peer_data.get("is_seed", False),
            )
            applied_peers += 1

        # 3) Reasociar peers a torrents
        for torrent in torrents:
            torrent_data = torrent.model_dump() if hasattr(torrent, "model_dump") else torrent
            info_hash = torrent_data.get("info_hash") or torrent_data.get("hash")
            for peer_id in torrent_data.get("peer_ids", []):
                try:
                    linked = await self.torrent_repo.add_peer_to_torrent(
                        info_hash=info_hash,
                        peer_identifier=peer_id,
                    )
                    if linked:
                        linked_relations += 1
                except Exception:
                    logger.debug(
                        f"No se pudo vincular peer {peer_id} al torrent {info_hash} desde snapshot",
                        exc_info=True,
                    )

        logger.info(
            f"Snapshot aplicado desde {source_tracker_id}: torrents={applied_torrents}, "
            f"peers={applied_peers}, links={linked_relations}"
        )

        return DataResponse(
            data={
                "status": "snapshot_applied",
                "source_tracker": source_tracker_id,
                "torrents_count": len(torrents),
                "peers_count": len(peers),
                "applied_torrents": applied_torrents,
                "applied_peers": applied_peers,
                "linked_relations": linked_relations,
                "vector_clock": vector_clock,
            }
        )
