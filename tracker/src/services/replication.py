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
from typing import Optional

from bit_lib.services import UniqueService, ClientService
from bit_lib.models import Request, Data, decode_request, process_header, EventSuccess

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
    ):
        super().__init__(host, port, EventHandler.endpoint)

        self.tracker_id = tracker_id
        self.cluster_service = cluster_service
        self.settings = settings

        # Mínimo de réplicas para cumplir tolerancia a fallos nivel 2
        self._min_replicas = 3

        # Tasks de loops
        self._replication_task: Optional[asyncio.Task] = None
        self._running = False

    # ==================== MessageService Abstract Methods ====================

    async def _handle_binary(self, protocol, meta, data: bytes):
        """Handle binary data transfer (e.g., snapshots)"""
        logger.warning(f"[{self.tracker_id}] Binary data received but not implemented yet")

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

    def _select_replica_targets(self, torrent_hash: str) -> list[TrackerState]:
        """
        Selecciona trackers destino para réplicas usando hash(torrent) mod N.

        Garantiza mínimo de 3 réplicas (tolerancia a fallos nivel 2).
        """
        active_trackers = self.cluster_service.get_active_trackers()

        if not active_trackers:
            return []

        # Ordenar determinísticamente por tracker_id
        sorted_trackers = sorted(active_trackers, key=lambda t: t.tracker_id)
        n = len(sorted_trackers)

        # Calcular número de réplicas (mínimo 3, máximo N disponibles)
        replica_count = min(self._min_replicas, n)

        # Particionado: hash(torrent) mod N como índice inicial
        start_idx = abs(hash(torrent_hash)) % n

        # Seleccionar trackers en anillo (circular)
        targets = []
        for i in range(replica_count):
            idx = (start_idx + i) % n
            targets.append(sorted_trackers[idx])

        return targets

    async def _replicate_events_to_tracker(
        self, tracker: TrackerState, events: list[EventLog]
    ) -> bool:
        """Envía batch de eventos a un tracker específico"""
        try:
            events_data = [ev.model_dump() for ev in events]

            req = Request(
                controller="Replication",
                command="update",
                func="replicate_events",
                args={
                    "source_tracker_id": self.tracker_id,
                    "events": events_data,
                },
            )

            response = await self.request(
                tracker.host, tracker.port, req, timeout=self.settings.timeout
            )

            if response and response.data:
                logger.debug(
                    f"[{self.tracker_id}] Replicated {len(events)} events to {tracker.tracker_id}"
                )
                return True

            return False

        except Exception as e:
            logger.warning(
                f"[{self.tracker_id}] Failed to replicate to {tracker.tracker_id}: {e}"
            )
            return False

    async def _replicate_pending_events(self):
        """Obtiene eventos pendientes y los replica a trackers responsables"""
        from src.repos import RepoContainer

        event_repo = RepoContainer.event_log_repo()

        # Obtener eventos pendientes de replicación
        pending = await event_repo.get_pending_replication(0)

        if not pending:
            return

        # Agrupar eventos por torrent_hash
        events_by_torrent: dict[str, list[EventLog]] = {}
        events_without_hash: list[EventLog] = []

        for event in pending:
            torrent_hash = self._extract_torrent_hash(event)
            if torrent_hash:
                if torrent_hash not in events_by_torrent:
                    events_by_torrent[torrent_hash] = []
                events_by_torrent[torrent_hash].append(event)
            else:
                # Eventos sin torrent_hash → replicar a todos
                events_without_hash.append(event)

        # Replicar eventos por torrent a trackers específicos
        for torrent_hash, events in events_by_torrent.items():
            targets = self._select_replica_targets(torrent_hash)

            for tracker in targets:
                success = await self._replicate_events_to_tracker(tracker, events)

                if success:
                    # Marcar eventos como replicados hacia este tracker
                    for event in events:
                        await event_repo.mark_replicated(event.id, tracker.tracker_id)

        # Eventos sin hash → broadcast a todos los trackers activos
        if events_without_hash:
            all_trackers = self.cluster_service.get_active_trackers()

            for tracker in all_trackers:
                success = await self._replicate_events_to_tracker(
                    tracker, events_without_hash
                )

                if success:
                    for event in events_without_hash:
                        await event_repo.mark_replicated(event.id, tracker.tracker_id)

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
        Enruta requests al ReplicationHandler.

        Los eventos externos primero pasan por EventHandler para validación,
        luego se despachan al ReplicationHandler para aplicación.
        """
        event_hdl = HandlerContainer.event_hdl()
        response = await event_hdl._exec_handler(hdl_key, data)

        if isinstance(response, EventSuccess):
            header, data = decode_request(response.request)
            _, hdl_key = process_header(header)

            handler = HandlerContainer.replication_hdl()
            return await handler.process(hdl_key, data, msg_id)
