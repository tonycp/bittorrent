"""
ClusterService - Coordinador de estabilidad del cluster de trackers.

Responsabilidades:
- Descubrimiento y mantenimiento de membresía (trackers activos)
- Elección de coordinador (Bully algorithm)
- Liveness/heartbeats y detección de fallos
- Exposición de la vista del cluster y estado de estabilidad
"""

import asyncio
import logging
from typing import Optional, Set, Tuple

from bit_lib.models.message import Request
from bit_lib.services import (
    UniqueService,
    ClientService,
    DockerDNSDiscovery,
    PingSweepDiscovery,
)

from src.settings.services import ClusterSettings
from src.handlers.cluster import ClusterHandler
from src.models import (
    ClusterState,
    TrackerState,
    ElectionResponse,
)
from bit_lib.context import CacheManager

logger = logging.getLogger(__name__)


class ClusterService(UniqueService, ClientService):
    """
    Servicio de cluster distribuido con Bully algorithm para elección.

    Flujo:
    1. Arranque: tracker se autoasigna como coordinador (cluster vacío)
    2. Discovery periódico: busca otros trackers via DNS Docker
    3. JOIN: intercambia estado con trackers encontrados
    4. Heartbeat: ping periódico para detectar caídas
    5. Election: Bully cuando hay cambios en cluster
    6. Cleanup: normalización de query_count si es coordinador
    """

    def __init__(
        self,
        host: str,
        port: int,
        cluster_state: ClusterState,
        settings: ClusterSettings,
    ):
        super().__init__(host, port, "Cluster")

        self.settings = settings
        self.cluster_state = cluster_state

        # Ensure cache is initialized to avoid NoneType errors
        if self.cluster_state.cache is None:
            self.cluster_state.cache = CacheManager(
                default_ttl=self.settings.liveness_timeout,
                name="cluster-cache",
            )

        # Discovery services
        self.dns_discovery = DockerDNSDiscovery(host, port)
        self.ping_discovery = PingSweepDiscovery(host, port)

        # Handler para procesar requests
        self.handler = ClusterHandler(self.cluster_state)

        # Tasks
        self._sync_task = None
        self._heartbeat_task = None
        self._cleanup_task = None

        # Lifecycle
        self._running = False

        # Election tracking
        self._coordinator_heartbeat_fails = 0  # Contador de fallos al coordinador

    async def start_cluster_sync(self):
        """Inicia loops de sync, heartbeat y cleanup"""
        logger.info(f"[{self.cluster_state.tracker_id}] Iniciando ClusterService")

        self._sync_task = asyncio.create_task(self._cluster_sync_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cluster_sync(self):
        """Detiene todos los loops"""
        for task in [self._sync_task, self._heartbeat_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def run(self):
        """Arranca loops y servidor RPC del cluster."""
        if self._running:
            return

        self._running = True
        await self.start_cluster_sync()

        try:
            await super().run()
        finally:
            self._running = False

    async def stop(self):
        """Detiene loops y servidor RPC del cluster."""
        await self.stop_cluster_sync()
        await super().stop()

    async def _dispatch_request(self, hdl_key: str, data, msg_id: str):
        """Enruta request al ClusterHandler"""
        return await self.handler.process(hdl_key, data, reply_to=msg_id)

    # ==================== MessageService Abstract Methods ====================

    async def _handle_binary(self, protocol, meta, data: bytes):
        """Handle binary data transfer (e.g., snapshots)"""
        logger.warning(f"[{self.cluster_state.tracker_id}] Binary data received but not implemented yet")

    async def _on_connect(self, protocol):
        """Called when a new connection is established"""
        logger.debug(f"[{self.cluster_state.tracker_id}] New connection established")

    async def _on_disconnect(self, protocol, exc: Optional[Exception]):
        """Called when a connection is closed"""
        if exc:
            logger.debug(f"[{self.cluster_state.tracker_id}] Connection closed with error: {exc}")
        else:
            logger.debug(f"[{self.cluster_state.tracker_id}] Connection closed cleanly")

    # ==================== Operaciones de Cluster ====================

    async def _discover_peers(self) -> Set[str]:
        """Busca trackers via Docker DNS, fallback a ping sweep"""
        peers = set()

        # Step 1: Intentar DockerDNS
        try:
            logger.debug(
                f"[{self.cluster_state.tracker_id}] Descubriendo via DockerDNS..."
            )
            ips = await self.dns_discovery.resolve_service(
                self.settings.service_name, use_cache=True
            )
            for ip in ips:
                if ip != self.host:  # No incluir a sí mismo
                    peers.add(f"{ip}:{self.settings.port}")
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] Descubierto via DNS: {ip}:{self.settings.port}"
                    )
        except Exception as e:
            logger.debug(
                f"[{self.cluster_state.tracker_id}] DockerDNS falló: {e}, intentando ping-sweep"
            )

        # Step 2: Fallback a PingSweep (solo si DockerDNS no encontró nada)
        if not peers:
            try:
                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Descubriendo via PingSweep..."
                )
                # Asumir subnet local 172.17.0.0/16 (Docker default) o 10.0.0.0/16
                subnet = "172.17.0.0/16"
                alive_peers = await self.ping_discovery.ping_range(
                    subnet, self.settings.port, max_workers=10, timeout=2.0
                )
                for ip, port in alive_peers:
                    if ip != self.host:  # No incluir a sí mismo
                        peers.add(f"{ip}:{port}")
                        logger.debug(
                            f"[{self.cluster_state.tracker_id}] Descubierto via PingSweep: {ip}:{port}"
                        )
            except Exception as e:
                logger.warning(
                    f"[{self.cluster_state.tracker_id}] PingSweep falló: {e}"
                )

        logger.info(
            f"[{self.cluster_state.tracker_id}] Discovery encontró {len(peers)} peers: {peers}"
        )
        return peers

    async def _send_join_request(self, host: str, port: int) -> Optional[TrackerState]:
        """Envía JOIN a tracker remoto"""
        try:
            # Construir estado local a enviar
            local_state = TrackerState.model_validate(
                self.cluster_state, from_attributes=True
            )
            local_state_dict = local_state.model_dump()

            req = Request(
                controller="Cluster",
                command="update",
                func="join",
                args={"remote": local_state_dict},
            )

            # Enviar JOIN via ClientService
            response = await self.request(host, port, req)

            if response.data:
                data = response.data
                new_coordinator = data.get("new_coordinator")
                if new_coordinator:
                    self.cluster_state.coordinator_id = new_coordinator
                    self.cluster_state.is_coordinator = (
                        new_coordinator == self.cluster_state.tracker_id
                    )
                return data.get("local_state")

            logger.debug(
                f"[{self.cluster_state.tracker_id}] JOIN enviado a {host}:{port}"
            )
            return None

        except Exception as e:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Error enviando JOIN a {host}:{port}: {e}"
            )
            return None

    async def _send_election_request(
        self,
        tracker: TrackerState,
        candidate_id: str,
        query_count: int,
    ) -> Optional[ElectionResponse]:
        """Envía solicitud de elección a un tracker. Devuelve ElectionResponse o None si falla."""
        try:
            req = Request(
                controller="Cluster",
                command="update",
                func="election",
                args={"candidate_id": candidate_id, "query_count": query_count},
            )

            response = await self.request(tracker.host, tracker.port, req)

            if response and response.data:
                data = response.data
                if isinstance(data, dict):
                    return ElectionResponse.model_validate(data)
                return data

            logger.debug(
                f"[{self.cluster_state.tracker_id}] Election req a {tracker.tracker_id}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Error enviando election a {tracker.tracker_id}: {e}"
            )
            return None

    # ==================== Heartbeat y Liveness ====================

    async def heartbeat_tracker(
        self, tracker_id: str
    ) -> Tuple[bool, Optional[str], Optional[bool]]:
        """
        Envía heartbeat a un tracker específico (público, reutilizable).

        Returns:
            (success, remote_coordinator_id, remote_is_coordinator)
        """
        try:
            tracker_state = await self.cluster_state.cache.get(tracker_id)
            if not tracker_state:
                logger.warning(
                    f"[{self.cluster_state.tracker_id}] Tracker {tracker_id} no en caché"
                )
                return False, None, None

            req = Request(
                controller="Cluster",
                command="update",
                func="heartbeat",
                args={
                    "tracker_id": self.cluster_state.tracker_id,
                    "query_count": self.cluster_state.query_count,
                    "vector_clock": self.cluster_state.vector_clock.to_dict(),
                },
            )

            response = await self.request(tracker_state.host, tracker_state.port, req)

            data = response.data if response and response.data else {}
            remote_coord = data.get("coordinator_id")
            remote_is_coord = data.get("is_coordinator")

            logger.debug(f"[{self.cluster_state.tracker_id}] Heartbeat a {tracker_id}")
            return True, remote_coord, remote_is_coord

        except Exception as e:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Heartbeat falló para {tracker_id}: {e}"
            )
            return False, None, None

    async def heartbeat_coordinator(self):
        # Enviar heartbeat y revisar respuesta
        success, remote_coord, remote_is_coord = await self.heartbeat_tracker(
            self.cluster_state.coordinator_id
        )

        if not success:
            # Fallo al coordinador
            self._coordinator_heartbeat_fails += 1
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Heartbeat al coordinador falló "
                f"({self._coordinator_heartbeat_fails} veces)"
            )

            # Si falló N veces, lanzar elección
            if (
                self._coordinator_heartbeat_fails
                >= self.settings.heartbeat_fail_threshold
            ):
                logger.info(
                    f"[{self.cluster_state.tracker_id}] Coordinador no responde, "
                    f"lanzando elección"
                )
                await self._trigger_election()
                self._coordinator_heartbeat_fails = 0
        else:
            # Éxito, resetear contador
            self._coordinator_heartbeat_fails = 0

            # Si el coordinador dice que ya no es líder, adoptamos el nuevo
            if remote_is_coord is False and remote_coord:
                logger.info(
                    f"[{self.cluster_state.tracker_id}] Coordinador reporta nuevo líder: {remote_coord}"
                )
                self.cluster_state.coordinator_id = remote_coord
                self.cluster_state.is_coordinator = (
                    remote_coord == self.cluster_state.tracker_id
                )

    # ==================== Operaciones de Elección ====================

    async def _trigger_election(self):
        """Desencadena elección consultando a peers (no confía solo en caché)."""
        peers = self.get_cluster_view()

        # Mi estado local como candidato inicial
        local_tracker = TrackerState.model_validate(
            self.cluster_state, from_attributes=True
        )
        best_candidate = (local_tracker.query_count, local_tracker.tracker_id)
        best_id = local_tracker.tracker_id
        # Si no hay peers, soy coordinador
        if not peers:
            self.cluster_state.is_coordinator = True
            self.cluster_state.coordinator_id = best_id
            return

        # Consultar a cada peer con RPC election en paralelo (similar a ping-sweep)
        semaphore = asyncio.Semaphore(self.settings.election_semaphore_size)

        async def _query_peer(peer: TrackerState):
            async with semaphore:
                return await self._send_election_request(
                    peer, best_id, best_candidate[0]
                )

        responses = await asyncio.gather(
            *[_query_peer(peer) for peer in peers], return_exceptions=False
        )

        for resp in responses:
            if not resp:
                continue  # peer no respondió, lo ignoramos
            candidate_tuple = (resp.query_count, resp.candidate_id)
            if candidate_tuple > best_candidate:
                best_candidate = candidate_tuple
                best_id = resp.candidate_id

        # Actualizar estado local con ganador
        was_coordinator = self.cluster_state.is_coordinator
        self.cluster_state.is_coordinator = best_id == self.cluster_state.tracker_id
        self.cluster_state.coordinator_id = best_id

        if was_coordinator and not self.cluster_state.is_coordinator:
            logger.info(
                f"[{self.cluster_state.tracker_id}] Perdí liderazgo, nuevo: {best_id}"
            )
        elif not was_coordinator and self.cluster_state.is_coordinator:
            logger.info(f"[{self.cluster_state.tracker_id}] Me convertí en coordinador")

    async def _normalize_query_counts(self):
        """Normaliza query_count de todos los trackers (solo ejecutar si eres coordinador)"""
        trackers = self.get_cluster_view()
        if not trackers:
            return

        query_counts = [t.query_count for t in trackers]
        avg = sum(query_counts) // len(query_counts) if query_counts else 0

        if avg == 0:
            return  # No hay nada que normalizar

        logger.info(f"[{self.cluster_state.tracker_id}] Normalizando con delta={avg}")

        # Enviar NORMALIZE a todos los trackers en paralelo
        semaphore = asyncio.Semaphore(self.settings.election_semaphore_size)

        async def _send_normalize(tracker: TrackerState):
            async with semaphore:
                try:
                    req = Request(
                        controller="Cluster",
                        command="update",
                        func="normalize",
                        args={"delta": avg},
                    )
                    await self.request(tracker.host, tracker.port, req)
                except Exception as e:
                    logger.warning(
                        f"[{self.cluster_state.tracker_id}] Error normalizando {tracker.tracker_id}: {e}"
                    )

        await asyncio.gather(
            *[_send_normalize(t) for t in trackers], return_exceptions=False
        )

    # ==================== Loops de Control ====================

    async def _cluster_sync_loop(self):
        """Loop de sync: cada sync_interval descubre e intenta JOIN con nuevos peers"""
        try:
            while True:
                await asyncio.sleep(self.settings.sync_interval)

                # Descubrir peers
                ips = await self._discover_peers()

                if not ips:
                    continue

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Discovery encontró: {ips}"
                )

                # Enviar JOINs a nuevos peers
                for ip in ips:
                    await self._send_join_request(ip, self.settings.port)

        except asyncio.CancelledError:
            logger.info(f"[{self.cluster_state.tracker_id}] Sync loop cancelado")
            raise
        except Exception as e:
            logger.error(f"[{self.cluster_state.tracker_id}] Error en sync loop: {e}")

    async def _heartbeat_loop(self):
        """Loop de heartbeat: cada heartbeat_interval verifica coordinador y detecta caídas"""
        try:
            while True:
                await asyncio.sleep(self.settings.heartbeat_interval)

                # Si no hay coordinador, skip
                if not self.cluster_state.coordinator_id:
                    continue

                # Si yo soy el coordinador, no me hago ping a mí mismo
                if self.cluster_state.coordinator_id == self.cluster_state.tracker_id:
                    self._coordinator_heartbeat_fails = 0
                    continue

                await self.heartbeat_coordinator()

        except asyncio.CancelledError:
            logger.info(f"[{self.cluster_state.tracker_id}] Heartbeat loop cancelado")
            raise
        except Exception as e:
            logger.error(
                f"[{self.cluster_state.tracker_id}] Error en heartbeat loop: {e}"
            )

    async def _cleanup_loop(self):
        """Loop de cleanup: cada cleanup_interval normaliza query_count (solo coordinador)"""
        try:
            while True:
                await asyncio.sleep(self.settings.cleanup_interval)

                if not self.cluster_state.is_coordinator:
                    continue  # Solo el coordinador limpia

                # Ejecutar normalización
                await self._normalize_query_counts()

        except asyncio.CancelledError:
            logger.info(f"[{self.cluster_state.tracker_id}] Cleanup loop cancelado")
            raise
        except Exception as e:
            logger.error(
                f"[{self.cluster_state.tracker_id}] Error en cleanup loop: {e}"
            )

    # ==================== Public API ====================

    def get_cluster_view(self):
        """Retorna trackers activos (no expirados)"""
        trackers: list[TrackerState] = []
        for _, tracker_state in self.cluster_state.cache.items():
            trackers.append(tracker_state)
        return trackers

    def get_active_trackers(self) -> list[TrackerState]:
        """Alias de get_cluster_view() para claridad semántica en ReplicationService"""
        return self.get_cluster_view()

    async def is_cluster_stable(self) -> bool:
        """Verifica si cluster es estable (al menos N trackers activos)"""
        return len(self.get_cluster_view()) >= self.settings.min_cluster_size

    async def get_coordinator(self) -> Optional[TrackerState]:
        """Retorna tracker elegido como coordinador"""
        if self.cluster_state.coordinator_id:
            return await self.cluster_state.cache.get(self.cluster_state.coordinator_id)
        return None

    async def get_tracker_by_id(self, tracker_id: str) -> Optional[TrackerState]:
        """Obtiene info de un tracker específico por ID desde el cache"""
        return await self.cluster_state.cache.get(tracker_id)

    async def is_tracker_alive(self, tracker_id: str) -> bool:
        """Verifica si un tracker específico está activo en el cluster"""
        tracker = await self.get_tracker_by_id(tracker_id)
        return tracker is not None

    def get_cluster_size(self) -> int:
        """Retorna cantidad de trackers activos (útil para cálculos de hash mod N)"""
        return len(self.get_cluster_view())
