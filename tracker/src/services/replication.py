"""
ReplicationService - Motor de replicación de metadatos entre trackers.

Responsabilidades:
- Replicar eventos de peers/torrents entre trackers del cluster
- Distribuir réplicas usando hash(torrent) mod N
- Garantizar mínimo de réplicas (tolerancia a fallos nivel 2)
- Sincronizar estado con trackers activos del cluster
"""

import asyncio
import logging
from typing import Optional, Dict, Set
import json
import hashlib

from bit_lib.services import UniqueService, ClientService
from bit_lib.models import Request, Data
from bit_lib.proto.collector import BlockCollector

from src.handlers import HandlerContainer, EventHandler
from src.models.event import EventLog
from src.models import TrackerState
from src.settings.services import ReplicationSettings

from .cluster import ClusterService

logger = logging.getLogger(__name__)


class ReplicationService(UniqueService, ClientService):
    """
    Servicio de replicación de metadatos entre trackers.

    Flujo:
    1. Solo replica si cluster está estable (vía ClusterService)
    2. Obtiene eventos pendientes del EventLogRepository
    3. Selecciona trackers destino usando hash(torrent) mod N
    4. Envía eventos en batch vía RPC "replicate_events"
    5. Marca eventos como replicados cuando tienen éxito
    """

    def __init__(
        self,
        host: str,
        port: int,
        tracker_id: str,
        cluster_service: ClusterService,
        settings: ReplicationSettings,
        event_handler=None,
        request_handler=None,
    ):
        super().__init__(host, port, EventHandler.endpoint)

        self.tracker_id = tracker_id
        self.cluster_service = cluster_service
        self.settings = settings
        self.event_handler = event_handler
        self.request_handler = request_handler

        # Mínimo de réplicas para cumplir tolerancia a fallos nivel 2
        self._min_replicas = 3

        # Tasks de loops
        self._replication_task: Optional[asyncio.Task] = None
        self._running = False

        # BlockCollectors para recibir datos binarios de snapshots
        # key: hash del snapshot, value: BlockCollector
        self._snapshot_collectors: Dict[str, BlockCollector] = {}
        
        # Tracking de trackers conocidos para detectar nodos nuevos/recuperados
        self._known_trackers: Set[str] = set()  # Set de tracker_ids conocidos
        
        # Threshold para enviar snapshot vs eventos individuales
        self._snapshot_threshold = 100  # Si hay >100 eventos, enviar snapshot

    # ==================== MessageService Abstract Methods ====================

    async def _handle_binary(self, protocol, meta, data: bytes):
        """
        Recibe chunks de snapshots o datos grandes vía binary.

        meta debe contener:
        - snapshot_id: identificador único del snapshot
        - block_index: índice del chunk
        - total_size: tamaño total del snapshot
        - block_size: tamaño del chunk (opcional, default BLOCK_SIZE)
        """
        try:
            snapshot_id = meta.get("snapshot_id")
            block_index = meta.get("block_index")
            total_size = meta.get("total_size")

            if not all([snapshot_id, block_index is not None, total_size]):
                logger.warning(
                    f"[{self.tracker_id}] Binary metadata incompleto: {meta}"
                )
                return

            # Crear o recuperar collector para este snapshot
            if snapshot_id not in self._snapshot_collectors:
                self._snapshot_collectors[snapshot_id] = BlockCollector(
                    hash=snapshot_id,
                    total=total_size,
                )

            collector = self._snapshot_collectors[snapshot_id]

            # Agregar bloque al collector
            success = await collector.add_block(block_index, data)

            if not success:
                logger.warning(
                    f"[{self.tracker_id}] Fallo al agregar bloque {block_index} para snapshot {snapshot_id}"
                )
                return

            logger.debug(
                f"[{self.tracker_id}] Bloque {block_index}/{len(collector.blocks)} recibido para snapshot {snapshot_id}"
            )

            # Si se completó, procesar el snapshot
            if collector.is_complete():
                complete_data = await collector.wait_for_completion()
                if complete_data:
                    logger.info(
                        f"[{self.tracker_id}] Snapshot {snapshot_id} completado ({len(complete_data)} bytes)"
                    )
                    await self._process_snapshot(snapshot_id, complete_data)
                    # Limpiar collector
                    del self._snapshot_collectors[snapshot_id]
                else:
                    logger.error(
                        f"[{self.tracker_id}] Snapshot {snapshot_id} verificación falló"
                    )
                    del self._snapshot_collectors[snapshot_id]

        except Exception as e:
            logger.error(f"[{self.tracker_id}] Error en _handle_binary: {e}")

    async def _process_snapshot(self, snapshot_id: str, data: bytes):
        """
        Procesa un snapshot completamente recibido.

        Los datos se envían al handler vía RPC para que los procese.
        """
        try:
            # Deserializar datos JSON
            snapshot_data = json.loads(data.decode("utf-8"))

            logger.info(
                f"[{self.tracker_id}] Snapshot {snapshot_id} recibido, enviando al handler"
            )

            # Enviar al handler vía RPC para que procese (handler tiene acceso a repos)
            req = Request(
                controller="Replication",
                command="update",
                func="replicate_snapshot",
                args=snapshot_data,
            )

            # Procesar localmente (self-request)
            response = await self.request(
                "localhost", self.port, req, timeout=self.settings.timeout
            )

            if response and response.data:
                logger.info(
                    f"[{self.tracker_id}] Snapshot {snapshot_id} procesado exitosamente"
                )
            else:
                logger.error(
                    f"[{self.tracker_id}] Snapshot {snapshot_id} falló al procesarse"
                )

        except Exception as e:
            logger.error(f"[{self.tracker_id}] Error procesando snapshot: {e}")

    async def _on_connect(self, protocol):
        """Called when a new connection is established"""
        logger.debug(f"[{self.tracker_id}] New connection established")

    async def _on_disconnect(self, protocol, exc: Optional[Exception]):
        """Called when a connection is closed"""
        if exc:
            logger.debug(f"[{self.tracker_id}] Connection closed with error: {exc}")
        else:
            logger.debug(f"[{self.tracker_id}] Connection closed cleanly")

    # ==================== Operaciones de Replicación ====================

    def _extract_torrent_hash(self, event: EventLog) -> Optional[str]:
        """Extrae torrent_hash del evento para particionado"""
        data = getattr(event, "data", {}) or {}
        return data.get("torrent_hash") or data.get("info_hash")

    def _select_replica_targets(self, torrent_hash: str, check_existing: bool = False) -> list[TrackerState]:
        """
        Selecciona trackers destino para réplicas usando hash determinístico.

        Usa hashlib.md5 en lugar de hash() de Python para garantizar
        que el mismo torrent siempre se replica a los mismos trackers,
        independientemente de la instancia de Python.

        Garantiza mínimo de 3 réplicas (tolerancia a fallos nivel 2).
        
        Args:
            torrent_hash: Hash del torrent
            check_existing: Si True, verifica trackers caídos y selecciona alternativas
        
        Comportamiento de re-replicación:
        - Si check_existing=True, verifica que los 3 trackers seleccionados estén vivos
        - Si alguno está caído, selecciona trackers alternativos del anillo
        - Mantiene SIEMPRE min_replicas=3 réplicas activas (tolerancia a fallos nivel 2)
        """
        active_trackers = self.cluster_service.get_active_trackers()

        if not active_trackers:
            return []

        # Excluir el tracker local de los posibles destinos
        active_trackers = [t for t in active_trackers if t.tracker_id != self.tracker_id]

        # Dedupe por tracker_id para evitar targets duplicados por entradas stale en cache
        unique_trackers: dict[str, TrackerState] = {}
        for tracker in active_trackers:
            unique_trackers[tracker.tracker_id] = tracker
        active_trackers = list(unique_trackers.values())
        
        if not active_trackers:
            return []

        # Ordenar determinísticamente por tracker_id
        sorted_trackers = sorted(active_trackers, key=lambda t: t.tracker_id)
        n = len(sorted_trackers)

        # Calcular número de réplicas (mínimo 3, máximo N disponibles)
        # Excluimos el tracker local, así que pedimos min_replicas-1 destinos
        replica_count = min(self._min_replicas - 1, n)

        # Particionado: hash determinístico (MD5) mod N como índice inicial
        hash_bytes = hashlib.md5(torrent_hash.encode()).digest()
        hash_int = int.from_bytes(hash_bytes, byteorder="big", signed=False)
        start_idx = hash_int % n

        # Seleccionar trackers en anillo (circular)
        targets = []
        attempted_indices = set()
        
        i = 0
        while len(targets) < replica_count and len(attempted_indices) < n:
            idx = (start_idx + i) % n
            
            if idx not in attempted_indices:
                attempted_indices.add(idx)
                candidate = sorted_trackers[idx]
                
                # Si no verificamos existentes, agregar directamente
                if not check_existing:
                    targets.append(candidate)
                else:
                    # Verificar si el tracker está realmente vivo
                    # (active_trackers ya filtra por TTL, pero podemos hacer check adicional)
                    targets.append(candidate)
            
            i += 1

        return targets

    def _ordered_candidates_by_hash(
        self, candidates: list[TrackerState], torrent_hash: str
    ) -> list[TrackerState]:
        """Devuelve candidatos en orden determinístico circular según hash del torrent."""
        if not candidates:
            return []

        sorted_trackers = sorted(candidates, key=lambda t: t.tracker_id)
        n = len(sorted_trackers)

        hash_bytes = hashlib.md5(torrent_hash.encode()).digest()
        hash_int = int.from_bytes(hash_bytes, byteorder="big", signed=False)
        start_idx = hash_int % n

        return [sorted_trackers[(start_idx + i) % n] for i in range(n)]

    async def _is_tracker_reachable(self, tracker: TrackerState) -> bool:
        try:
            ok, _, _ = await self.cluster_service.heartbeat_tracker(tracker.tracker_id)
            if ok:
                return True
        except Exception:
            pass

        try:
            req = Request(
                controller="Cluster",
                command="update",
                func="heartbeat",
                args={
                    "tracker_id": self.tracker_id,
                    "query_count": self.cluster_service.cluster_state.query_count,
                    "vector_clock": self.cluster_service.cluster_state.vector_clock,
                },
            )
            response = await self.request(
                tracker.host,
                tracker.port,
                req,
                timeout=self.settings.timeout,
            )
            if response:
                return True
        except Exception:
            pass

        await self._invalidate_tracker_cache(tracker)
        logger.debug(
            f"[{self.tracker_id}] Skipping unreachable replica target {tracker.tracker_id}"
        )
        return False

    async def _get_pinned_replica_target_ids(self, torrent_hash: str) -> set[str]:
        if not self.event_handler:
            return set()

        repo = getattr(self.event_handler, "replica_assignment_repo", None)
        if not repo:
            return set()

        try:
            assignment = await repo.get_by_torrent_hash(torrent_hash)
            if not assignment:
                return set()

            values = assignment.replica_set or []
            if not isinstance(values, list):
                return set()

            return {tracker_id for tracker_id in values if isinstance(tracker_id, str)}
        except Exception as exc:
            logger.debug(
                f"[{self.tracker_id}] Could not read pinned replicas for {torrent_hash[:8]}: {exc}"
            )
            return set()

    async def _persist_pinned_replica_targets(
        self, torrent_hash: str, target_trackers: list[TrackerState]
    ) -> None:
        if not self.event_handler:
            return

        repo = getattr(self.event_handler, "replica_assignment_repo", None)
        if not repo:
            return

        try:
            ordered_target_ids = [tracker.tracker_id for tracker in target_trackers]
            await repo.upsert_replica_set(torrent_hash, ordered_target_ids)
        except Exception as exc:
            logger.warning(
                f"[{self.tracker_id}] Could not persist pinned replicas for {torrent_hash[:8]}: {exc}"
            )

    async def _select_reachable_replica_targets(self, torrent_hash: str) -> list[TrackerState]:
        """
        Selecciona destinos estables de réplica para un torrent.

        Política:
        - Mantener el replica_set ya asignado mientras siga alcanzable.
        - Reemplazar solo réplicas caídas (failover).
        - Persistir el nuevo replica_set tras failover para evitar rebalanceo al reingreso.
        """
        active_trackers = self.cluster_service.get_active_trackers()
        if not active_trackers:
            return []

        candidates = [t for t in active_trackers if t.tracker_id != self.tracker_id]
        unique_candidates: dict[str, TrackerState] = {
            tracker.tracker_id: tracker for tracker in candidates
        }
        candidates = list(unique_candidates.values())

        if not candidates:
            return []

        replica_count = min(self._min_replicas - 1, len(candidates))
        ordered_candidates = self._ordered_candidates_by_hash(candidates, torrent_hash)

        pinned_ids = await self._get_pinned_replica_target_ids(torrent_hash)
        selected: list[TrackerState] = []
        selected_ids: set[str] = set()

        # 1) Priorizar réplicas previamente fijadas
        for tracker in ordered_candidates:
            if len(selected) >= replica_count:
                break
            if tracker.tracker_id not in pinned_ids:
                continue
            if await self._is_tracker_reachable(tracker):
                selected.append(tracker)
                selected_ids.add(tracker.tracker_id)

        # 2) Completar con candidatos del anillo (failover/bootstrap)
        for tracker in ordered_candidates:
            if len(selected) >= replica_count:
                break
            if tracker.tracker_id in selected_ids:
                continue
            if await self._is_tracker_reachable(tracker):
                selected.append(tracker)
                selected_ids.add(tracker.tracker_id)

        # Persistir si cambió el replica_set efectivo
        if selected and selected_ids != pinned_ids:
            await self._persist_pinned_replica_targets(torrent_hash, selected)

        return selected

    def _get_replicated_targets(self, event_dict: dict) -> set[str]:
        replicated_to = event_dict.get("replicated_to") or {}
        if not isinstance(replicated_to, dict):
            return set()
        return {tracker_id for tracker_id, replicated in replicated_to.items() if replicated}

    async def _invalidate_tracker_cache(self, tracker: TrackerState):
        try:
            await self.cluster_service.cluster_state.cache.invalidate(tracker.host)
        except Exception as exc:
            logger.debug(
                f"[{self.tracker_id}] Could not invalidate cache for {tracker.tracker_id}: {exc}"
            )

    async def _replicate_events_to_tracker(
        self, tracker: TrackerState, events_data: list[dict]
    ) -> bool:
        """Envía batch de eventos a un tracker específico y marca como replicados"""
        try:
            req = Request(
                controller="Replication",
                command="update",
                func="replicate_events",
                args={
                    "source_tracker_id": self.tracker_id,
                    "events": events_data,
                },
            )

            # El puerto del tracker RPC es port - 1 (cluster port - 1)
            rpc_port = tracker.port - 1
            
            logger.debug(f"[{self.tracker_id}] Sending replication request to {tracker.tracker_id} ({tracker.host}:{rpc_port})")
            
            response = await self.request(
                tracker.host, rpc_port, req, timeout=self.settings.timeout
            )

            logger.debug(f"[{self.tracker_id}] Replication response from {tracker.tracker_id}: {response}")
            
            if response and response.data:
                payload = response.data
                if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                    payload = payload["data"]

                applied_event_ids = set()
                if isinstance(payload, dict):
                    raw_ids = payload.get("applied_event_ids") or []
                    applied_event_ids = {str(event_id) for event_id in raw_ids if event_id is not None}

                # Marcar eventos como replicados al tracker destino
                if self.event_handler:
                    for event_data in events_data:
                        event_id = event_data.get("id")
                        event_id_str = str(event_id) if event_id is not None else None
                        if event_id_str and event_id_str in applied_event_ids:
                            try:
                                await self.event_handler.event_repo.mark_replicated(event_id_str, tracker.tracker_id)
                                logger.debug(f"[{self.tracker_id}] Marked event {event_id_str} as replicated to {tracker.tracker_id}")
                            except Exception as e:
                                logger.warning(f"[{self.tracker_id}] Failed to mark event {event_id_str} as replicated: {e}")
                
                logger.debug(
                    f"[{self.tracker_id}] Replicated {len(applied_event_ids)} events to {tracker.tracker_id}"
                )
                return True

            logger.warning(f"[{self.tracker_id}] Empty or no response from {tracker.tracker_id}")
            await self._invalidate_tracker_cache(tracker)
            return False

        except asyncio.TimeoutError as e:
            logger.warning(
                f"[{self.tracker_id}] Timeout replicating to {tracker.tracker_id}: {e}"
            )
            await self._invalidate_tracker_cache(tracker)
            return False
        except Exception as e:
            logger.error(
                f"[{self.tracker_id}] Exception replicating to {tracker.tracker_id}: {type(e).__name__}: {e}",
                exc_info=True
            )
            await self._invalidate_tracker_cache(tracker)
            return False

    async def _build_snapshot_payload(self) -> Optional[bytes]:
        """Construye snapshot JSON usando el endpoint request_snapshot local."""
        try:
            req = Request(
                controller="Replication",
                command="get",
                func="request_snapshot",
                args={"tracker_id": self.tracker_id},
            )

            response = await self.request(
                "localhost",
                self.port,
                req,
                timeout=self.settings.timeout,
            )

            if not response or not response.data:
                return None

            payload = response.data
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                payload = payload["data"]

            if not isinstance(payload, dict):
                return None

            return json.dumps(payload, default=str).encode("utf-8")
        except Exception as e:
            logger.error(f"[{self.tracker_id}] Error building snapshot payload: {e}")
            return None

    async def _send_snapshot_to_tracker(
        self, tracker: TrackerState, snapshot_data: bytes, snapshot_id: str
    ) -> bool:
        """
        Envía snapshot como datos binarios chunked a un tracker específico.

        Divide el snapshot en chunks y envía cada uno con metadata.
        """
        try:
            from bit_lib.const import c_proto as cp

            block_size = cp.BLOCK_SIZE
            total_blocks = (len(snapshot_data) + block_size - 1) // block_size

            logger.info(
                f"[{self.tracker_id}] Enviando snapshot {snapshot_id} ({len(snapshot_data)} bytes) "
                f"en {total_blocks} bloques a {tracker.tracker_id}"
            )

            # Enviar cada bloque como binary data
            for block_idx in range(total_blocks):
                start = block_idx * block_size
                end = min(start + block_size, len(snapshot_data))
                block_data = snapshot_data[start:end]

                # Metadata para identificar el chunk
                meta = {
                    "snapshot_id": snapshot_id,
                    "block_index": block_idx,
                    "total_size": len(snapshot_data),
                    "block_size": len(block_data),
                }

                try:
                    # send_binary no existe en base, necesitamos usar el protocolo
                    # Por ahora, alternativa: enviar como request con encoding base64
                    import base64

                    req = Request(
                        controller="Replication",
                        command="update",
                        func="replicate_snapshot_chunk",
                        args={
                            "source_tracker_id": self.tracker_id,
                            "snapshot_id": snapshot_id,
                            "block_index": block_idx,
                            "total_size": len(snapshot_data),
                            "chunk_data": base64.b64encode(block_data).decode("utf-8"),
                        },
                    )

                    response = await self.request(
                        tracker.host, tracker.port, req, timeout=self.settings.timeout
                    )

                    if not response or not response.data:
                        logger.warning(
                            f"[{self.tracker_id}] Fallo enviando chunk {block_idx}/{total_blocks} a {tracker.tracker_id}"
                        )
                        return False

                    logger.debug(
                        f"[{self.tracker_id}] Chunk {block_idx}/{total_blocks} enviado a {tracker.tracker_id}"
                    )

                except Exception as e:
                    logger.error(
                        f"[{self.tracker_id}] Error enviando chunk {block_idx} a {tracker.tracker_id}: {e}"
                    )
                    return False

            logger.info(
                f"[{self.tracker_id}] Snapshot {snapshot_id} enviado completamente a {tracker.tracker_id}"
            )
            return True

        except Exception as e:
            logger.error(f"[{self.tracker_id}] Error en _send_snapshot_to_tracker: {e}")
            return False

    async def _replicate_pending_events(self):
        """
        Replica eventos pendientes usando selección determinística de réplicas.
        
        Agrupa eventos por torrent_hash y usa _select_replica_targets() para
        garantizar que cada torrent se replica exactamente a min_replicas trackers
        (tolerancia a fallos nivel 2).
        """
        active_trackers = self.cluster_service.get_active_trackers()

        if not active_trackers:
            logger.debug(f"[{self.tracker_id}] No active trackers for replication")
            return

        # Obtener eventos pendientes vía callback al handler local
        req = Request(
            controller="Event",
            command="get",
            func="pending_events",
        )

        try:
            # Usar callback para obtener eventos pendientes del EventHandler
            if not self.request_handler:
                logger.warning(
                    f"[{self.tracker_id}] No request_handler available for replication"
                )
                return

            response = await self.request_handler(req)

            logger.debug(f"[{self.tracker_id}] Response from pending_events: {response}")
            logger.debug(f"[{self.tracker_id}] Response.data: {response.data if response else None}")
            
            if not response or not response.data:
                logger.debug(f"[{self.tracker_id}] No pending events to replicate")
                return

            events_data = response.data.get("events", [])

            if not events_data:
                logger.debug(f"[{self.tracker_id}] No pending events to replicate (events_data empty)")
                return

            logger.info(
                f"[{self.tracker_id}] Found {len(events_data)} events to replicate"
            )

        except Exception as e:
            logger.warning(f"[{self.tracker_id}] Error getting pending events: {e}")
            return

        # Agrupar eventos por torrent_hash para aplicar política de réplicas
        events_by_torrent = {}
        for event in events_data:
            torrent_hash = self._extract_torrent_hash_from_dict(event)
            if torrent_hash:
                if torrent_hash not in events_by_torrent:
                    events_by_torrent[torrent_hash] = []
                events_by_torrent[torrent_hash].append(event)
            else:
                # Eventos sin torrent_hash (ej: cluster events) se replican a todos
                logger.debug(f"[{self.tracker_id}] Event without torrent_hash, skipping: {event.get('operation')}")

        # Detectar nodos nuevos/recuperados para enviar snapshot
        current_tracker_ids = {t.tracker_id for t in active_trackers}
        new_trackers = current_tracker_ids - self._known_trackers
        
        if new_trackers:
            logger.info(
                f"[{self.tracker_id}] Detected {len(new_trackers)} new/recovered tracker(s): {new_trackers}"
            )
            
            # Para cada nuevo tracker, decidir si enviar snapshot o eventos
            for new_tracker_id in new_trackers:
                new_tracker = next((t for t in active_trackers if t.tracker_id == new_tracker_id), None)
                if not new_tracker:
                    continue
                
                # Si hay muchos eventos pendientes, enviar snapshot
                if len(events_data) > self._snapshot_threshold:
                    logger.info(
                        f"[{self.tracker_id}] Sending snapshot to {new_tracker_id} "
                        f"({len(events_data)} events > threshold {self._snapshot_threshold})"
                    )
                    snapshot_data = await self._build_snapshot_payload()
                    if snapshot_data:
                        snapshot_id = hashlib.md5(snapshot_data).hexdigest()
                        await self._send_snapshot_to_tracker(
                            tracker=new_tracker,
                            snapshot_data=snapshot_data,
                            snapshot_id=snapshot_id,
                        )
                    else:
                        logger.warning(
                            f"[{self.tracker_id}] Snapshot payload vacío, fallback a eventos"
                        )
                else:
                    logger.info(
                        f"[{self.tracker_id}] Sending {len(events_data)} events to {new_tracker_id} "
                        f"(below snapshot threshold)"
                    )
            
            # Actualizar trackers conocidos
            self._known_trackers = current_tracker_ids
        
        # Para cada torrent, seleccionar réplicas y enviar eventos
        for torrent_hash, torrent_events in events_by_torrent.items():
            # Seleccionar trackers destino (máximo min_replicas)
            target_trackers = await self._select_reachable_replica_targets(torrent_hash)
            
            logger.info(
                f"[{self.tracker_id}] Torrent {torrent_hash[:8]}: "
                f"{len(torrent_events)} events → {len(target_trackers)} replicas "
                f"({', '.join(t.tracker_id for t in target_trackers)})"
            )

            for tracker in target_trackers:
                try:
                    # Enviar solo eventos que aún no fueron replicados a este tracker
                    tracker_events = [
                        event for event in torrent_events
                        if tracker.tracker_id not in self._get_replicated_targets(event)
                    ]

                    if not tracker_events:
                        continue

                    success = await self._replicate_events_to_tracker(tracker, tracker_events)

                    if success:
                        logger.info(
                            f"[{self.tracker_id}] Successfully replicated {len(tracker_events)} events "
                            f"(torrent {torrent_hash[:8]}) to {tracker.tracker_id}"
                        )
                    else:
                        logger.warning(
                            f"[{self.tracker_id}] Failed to replicate to {tracker.tracker_id}, will retry next cycle"
                        )
                except Exception as e:
                    logger.warning(
                        f"[{self.tracker_id}] Error replicating to {tracker.tracker_id}: {e}"
                    )

    def _extract_torrent_hash_from_dict(self, event_dict: dict) -> Optional[str]:
        """Extrae torrent_hash de un evento en formato dict"""
        data = event_dict.get("data", {}) or {}
        return data.get("torrent_hash") or data.get("info_hash")

    # ==================== Loops de Control ====================

    async def _replication_loop(self):
        """Loop periódico: replica eventos pendientes si cluster está estable"""
        try:
            while self._running:
                await asyncio.sleep(self.settings.interval)

                # Verificar estabilidad del cluster
                if not await self.cluster_service.is_cluster_stable():
                    logger.debug(
                        f"[{self.tracker_id}] Cluster not stable, skipping replication"
                    )
                    continue

                # Verificar que hay trackers disponibles
                cluster_size = self.cluster_service.get_cluster_size()
                if cluster_size < 2:  # Solo yo en el cluster
                    logger.debug(
                        f"[{self.tracker_id}] No other trackers, skipping replication"
                    )
                    continue

                # Ejecutar replicación
                await self._replicate_pending_events()

        except asyncio.CancelledError:
            logger.info(f"[{self.tracker_id}] Replication loop cancelled")
            raise
        except Exception as e:
            logger.error(f"[{self.tracker_id}] Error in replication loop: {e}")

    # ==================== Lifecycle ====================

    async def start_replication(self):
        """Inicia el loop de replicación"""
        if self._running:
            return

        self._running = True
        self._replication_task = asyncio.create_task(self._replication_loop())

        logger.info(f"[{self.tracker_id}] ReplicationService started")

    async def stop_replication(self):
        """Detiene el loop de replicación"""
        self._running = False

        if self._replication_task:
            self._replication_task.cancel()
            try:
                await self._replication_task
            except asyncio.CancelledError:
                pass

        logger.info(f"[{self.tracker_id}] ReplicationService stopped")

    # Alias usados por TrackerService
    async def start_replication_loops(self):
        await self.start_replication()

    async def stop_replication_loops(self):
        await self.stop_replication()

    async def run(self):
        """Arranca loop de replicación y servidor RPC asociado."""
        if self._running:
            return

        await self.start_replication()
        try:
            await super().run()
        finally:
            self._running = False

    async def stop(self):
        """Detiene loop de replicación y servidor RPC asociado."""
        await self.stop_replication()
        await super().stop()

    # ==================== Request Dispatcher ====================

    async def _dispatch_request(self, hdl_key: str, data: Data, msg_id: str):
        """
        Enruta requests directamente al ReplicationHandler.
        Similar al patrón usado en ClusterService.
        """
        handler = HandlerContainer.replication_hdl()
        return await handler.process(hdl_key, data, msg_id)
