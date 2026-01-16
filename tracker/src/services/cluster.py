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
from dataclass_mapper import map_to

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
        self.dns_discovery = DockerDNSDiscovery(host, settings.discovery_port)
        self.ping_discovery = PingSweepDiscovery(host, settings.discovery_port)

        # Handler para procesar requests
        self.handler = ClusterHandler(self.cluster_state)

        # Tasks
        self._sync_task = None
        self._heartbeat_task = None
        self._cleanup_task = None
        self._ping_task = None

        # Per-IP semaphores to serialize requests to same tracker
        self._ip_semaphores: dict[str, asyncio.Semaphore] = {}
        self._semaphore_lock = asyncio.Lock()  # Protege acceso a _ip_semaphores

        # Lifecycle
        self._running = False

        # Election tracking
        self._coordinator_heartbeat_fails = 0  # Contador de fallos al coordinador

        # Stability tracking
        self._last_coordinator_change = (
            None  # Timestamp del último cambio de coordinador
        )
        self._cluster_stable = True  # Si el cluster está estable, al principio siempre esta estable (sin cambios por 5s)
        self._stability_threshold = 5.0  # Segundos sin cambios para considerar estable

    async def start_cluster_sync(self):
        """Inicia loops de sync, heartbeat y cleanup"""
        logger.info(f"[{self.cluster_state.tracker_id}] Iniciando ClusterService")

        self._sync_task = asyncio.create_task(self._cluster_sync_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._ping_task = asyncio.create_task(self.ping_discovery.run())

    async def stop_cluster_sync(self):
        """Detiene todos los loops"""
        for task in [
            self._sync_task,
            self._heartbeat_task,
            self._cleanup_task,
            self._ping_task,
        ]:
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
        logger.info(
            f"[{self.cluster_state.tracker_id}] Starting cluster service on {self.host}:{self.port}"
        )

        # Start sync, heartbeat, cleanup loops
        await self.start_cluster_sync()

        try:
            # Start cluster server listening for peer messages
            logger.info(f"[{self.cluster_state.tracker_id}] Starting cluster server...")
            await super().run()
        except asyncio.CancelledError:
            logger.info(f"[{self.cluster_state.tracker_id}] Cluster service cancelled")
            raise
        except Exception as e:
            logger.error(
                f"[{self.cluster_state.tracker_id}] Cluster service error: {e}"
            )
            raise
        finally:
            self._running = False
            logger.info(f"[{self.cluster_state.tracker_id}] Stopping cluster sync...")
            await self.stop_cluster_sync()

    async def stop(self):
        """Detiene loops y servidor RPC del cluster."""
        await self.stop_cluster_sync()
        await super().stop()

    async def _dispatch_request(self, hdl_key: str, data, msg_id: str):
        """Enruta request al ClusterHandler"""
        logger.debug(
            f"[{self.cluster_state.tracker_id}] _dispatch_request: "
            + f"hdl_key={hdl_key}"
            + f"data={data}"
        )
        return await self.handler.process(hdl_key, data, reply_to=msg_id)

    async def _process_request(self, request: Request):
        """Handle cluster requests"""
        logger.debug(
            f"[{self.cluster_state.tracker_id}] _process_request: controller={request.controller}, command={request.command}, func={request.func}"
        )

        logger.info(
            f"[{self.cluster_state.tracker_id}] Processing Cluster request: {request}"
        )
        # Route to parent for standard request processing
        return await super()._process_request(request)

    async def _get_ip_semaphore(self, ip: str) -> asyncio.Semaphore:
        """Get or create a semaphore for a given IP to serialize requests"""
        async with self._semaphore_lock:
            if ip not in self._ip_semaphores:
                self._ip_semaphores[ip] = asyncio.Semaphore(1)  # Una operación por vez
            return self._ip_semaphores[ip]

    # ==================== MessageService Abstract Methods ====================

    async def _handle_binary(self, protocol, meta, data: bytes):
        """Handle binary data transfer (e.g., snapshots)"""
        logger.warning(
            f"[{self.cluster_state.tracker_id}] Binary data received but not implemented yet"
        )

    async def _on_connect(self, protocol):
        """Called when a new connection is established"""
        logger.debug(f"[{self.cluster_state.tracker_id}] New connection established")

    async def _on_disconnect(self, protocol, exc: Optional[Exception]):
        """Called when a connection is closed"""
        if exc:
            logger.debug(
                f"[{self.cluster_state.tracker_id}] Connection closed with error: {exc}"
            )
        else:
            logger.debug(f"[{self.cluster_state.tracker_id}] Connection closed cleanly")

    # ==================== Operaciones de Cluster ====================

    async def _force_resync(self):
        """Fuerza redescubrimiento y JOIN con todos los peers (no solo nuevos)"""
        logger.info(
            f"[{self.cluster_state.tracker_id}] Forzando resync con todos los peers..."
        )

        # Discover all peers (not just new)
        ips = await self._discover_peers()

        # Also add any that were in cache before clearing
        all_ips = set(ips)

        # Send JOINs to everyone
        for ip in all_ips:
            host, port_str = ip.split(":", 1)
            await self._send_join_request(host, int(port_str))

        logger.info(
            f"[{self.cluster_state.tracker_id}] Resync completado con {len(all_ips)} peers"
        )

    # ==================== Operaciones de Cluster ====================

    async def _discover_peers(self) -> Set[str]:
        """Busca trackers via Docker DNS, fallback a ping sweep. Retorna solo NUEVOS (no en cluster cache)"""
        peers = set()
        service_name = self.settings.service_name

        # Step 1: DockerDNS
        try:
            logger.debug(
                f"[{self.cluster_state.tracker_id}] Descubriendo via DockerDNS..."
            )
            ips = await self.dns_discovery.resolve_service(
                service_name,
                use_cache=True,
                return_new_only=False,
            )
            new_count = 0
            refreshed_count = 0

            for ip in ips:
                if ip != self.host:  # No incluir a sí mismo
                    # Check if already in cluster cache
                    tracker_key = f"{ip}"  # Usar IP como key en cache
                    if await self.cluster_state.cache.touch(tracker_key):
                        refreshed_count += 1
                    else:
                        # No estaba en cache, es genuinamente nuevo
                        peers.add(f"{ip}:{self.port}")
                        new_count += 1

            if ips:
                logger.debug(
                    f"[{self.cluster_state.tracker_id}] DockerDNS: {len(ips)} IPs, "
                    f"nuevos={new_count}, refreshed={refreshed_count}"
                )
        except Exception as e:
            logger.debug(f"[{self.cluster_state.tracker_id}] DockerDNS falló: {e}")

        # Step 2: PingSweep (fallback if DNS found nothing)
        if not peers:
            try:
                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Descubriendo via PingSweep..."
                )
                subnet = self.settings.discovery_ping_subnet
                alive_peers = await self.ping_discovery.ping_range(
                    subnet,
                    self.settings.discovery_port,
                    max_workers=self.settings.discovery_ping_max_workers,
                    timeout=self.settings.discovery_timeout,
                    use_cache=True,
                    return_new_only=False,
                )
                first_ip = None
                last_ip = None
                new_count = 0
                refreshed_count = 0

                for ip, _ in alive_peers:
                    if ip != self.host:  # No incluir a sí mismo
                        if first_ip is None:
                            first_ip = ip
                        last_ip = ip

                        # Check if already in cluster cache
                        tracker_key = f"{ip}"
                        if await self.cluster_state.cache.touch(tracker_key):
                            refreshed_count += 1
                        else:
                            # No estaba en cache, es genuinamente nuevo
                            peers.add(f"{ip}:{self.port}")
                            new_count += 1

                if first_ip:
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] PingSweep: rango {first_ip}-{last_ip}, "
                        f"nuevos={new_count}, refreshed={refreshed_count}"
                    )
            except Exception as e:
                logger.warning(
                    f"[{self.cluster_state.tracker_id}] PingSweep falló: {e}"
                )

        if peers:
            logger.info(
                f"[{self.cluster_state.tracker_id}] Discovery encontró {len(peers)} nuevos peers: {peers}"
            )

        return peers

    async def _send_join_request(self, host: str, port: int) -> Optional[TrackerState]:
        """Envía JOIN a tracker remoto"""
        # Serializar requests al mismo IP
        semaphore = await self._get_ip_semaphore(host)
        async with semaphore:
            try:
                # Construir estado local a enviar (ya incluye coordinator_id y coordinator_tracker_id)
                local_state = map_to(self.cluster_state, TrackerState)
                # Serializar completamente, incluyendo VectorClock
                local_state_dict = local_state.model_dump()

                req = Request(
                    controller="Cluster",
                    command="update",
                    func="join",
                    args={
                        "remote": local_state_dict
                    },  # Pasar como 'remote' para que el handler lo reciba
                )

                # Enviar JOIN via ClientService
                response = await self.request(host, port, req)

                if response and response.data:
                    data = response.data
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] JOIN response data: {data}"
                    )

                    # The actual data is nested in response.data['data']
                    actual_data = data.get("data") if isinstance(data, dict) else None
                    if not actual_data:
                        # Fallback if structure is different
                        actual_data = data

                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] actual_data: {actual_data}"
                    )

                    new_coordinator = (
                        actual_data.get("new_coordinator") if actual_data else None
                    )
                    new_coordinator_ip = (
                        actual_data.get("new_coordinator_ip") if actual_data else None
                    )
                    if new_coordinator and new_coordinator_ip:
                        # Detectar cambio de coordinador para marcar inestabilidad
                        coordinator_changed = (
                            self.cluster_state.coordinator_tracker_id != new_coordinator
                        )

                        self.cluster_state.coordinator_id = new_coordinator_ip
                        self.cluster_state.coordinator_tracker_id = new_coordinator
                        self.cluster_state.is_coordinator = (
                            new_coordinator == self.cluster_state.tracker_id
                        )

                        if coordinator_changed:
                            self._last_coordinator_change = (
                                asyncio.get_event_loop().time()
                            )
                            self._cluster_stable = False
                            logger.info(
                                f"[{self.cluster_state.tracker_id}] 🔔 COORDINADOR ACTUALIZADO: {new_coordinator} | YO SOY COORDINADOR: {self.cluster_state.is_coordinator}"
                            )
                        else:
                            logger.debug(
                                f"[{self.cluster_state.tracker_id}] Coordinador confirmado: {new_coordinator}"
                            )

                        # Agregar coordinador al caché para heartbeats posteriores
                        coordinator_host = (
                            actual_data.get("coordinator_host") if actual_data else None
                        )
                        coordinator_port = (
                            actual_data.get("coordinator_port") if actual_data else None
                        )
                        if coordinator_host and coordinator_port:
                            try:
                                coordinator_state = TrackerState(
                                    tracker_id=new_coordinator,
                                    host=coordinator_host,
                                    port=coordinator_port,
                                )
                                await self.cluster_state.cache.set(
                                    new_coordinator_ip, coordinator_state
                                )
                                logger.debug(
                                    f"[{self.cluster_state.tracker_id}] Coordinador agregado a caché: {new_coordinator} ({coordinator_host}:{coordinator_port})"
                                )
                            except Exception as e:
                                logger.error(
                                    f"[{self.cluster_state.tracker_id}] Error creando coordinador: {e}"
                                )

                    # Extract remote tracker info from response to add to cache
                    local_state_data = (
                        actual_data.get("local_state") if actual_data else None
                    )
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] local_state_data type: {type(local_state_data)}, value: {local_state_data}"
                    )
                    if local_state_data:
                        try:
                            remote_tracker = TrackerState.model_validate(
                                local_state_data
                            )
                            # Usar IP como clave para consistencia con _discover_peers
                            cache_key = f"{remote_tracker.host}"
                            await self.cluster_state.cache.set(
                                cache_key, remote_tracker
                            )
                            logger.info(
                                f"[{self.cluster_state.tracker_id}] Agregado a caché: {remote_tracker.tracker_id} ({remote_tracker.host}:{remote_tracker.port})"
                            )
                        except Exception as e:
                            logger.error(
                                f"[{self.cluster_state.tracker_id}] Error validando remote_tracker: {e}",
                                exc_info=True,
                            )
                else:
                    logger.warning(
                        f"[{self.cluster_state.tracker_id}] JOIN response sin data"
                    )

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] JOIN enviado a {host}:{port}"
                )
                return data

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
        # Serializar requests al mismo IP
        try:
            req = Request(
                controller="Cluster",
                command="update",
                func="election",
                args={"candidate_id": candidate_id, "query_count": query_count},
            )

            logger.debug(
                f"[{self.cluster_state.tracker_id}] Enviando Election a {tracker.tracker_id}..."
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
                f"[{self.cluster_state.tracker_id}] Error enviando Election a {tracker.tracker_id}: {e}"
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

            # Serializar requests al mismo IP
            semaphore = await self._get_ip_semaphore(tracker_state.host)
            async with semaphore:
                req = Request(
                    controller="Cluster",
                    command="update",
                    func="heartbeat",
                    args={
                        "tracker_id": self.cluster_state.tracker_id,
                        "query_count": self.cluster_state.query_count,
                        "vector_clock": self.cluster_state.vector_clock,
                    },
                )

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Enviando Heartbeat a {tracker_id}..."
                )

                response = await self.request(
                    tracker_state.host, tracker_state.port, req
                )

                data = response.data if response and response.data else {}
                remote_coord = data.get("coordinator_id")
                remote_is_coord = data.get("is_coordinator")

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Heartbeat a {tracker_id}"
                )
                return True, remote_coord, remote_is_coord

        except Exception as e:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Heartbeat falló para {tracker_id}: {e}"
            )
            return False, None, None

    async def heartbeat_coordinator(self):
        # coordinator_id es ahora la IP del coordinador
        if not self.cluster_state.coordinator_id:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] No hay coordinador conocido"
            )
            return

        # Obtener el tracker del coordinador desde caché
        coordinator_tracker = await self.cluster_state.cache.get(
            self.cluster_state.coordinator_id
        )
        if not coordinator_tracker:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Coordinador {self.cluster_state.coordinator_tracker_id} "
                f"({self.cluster_state.coordinator_id}) no en caché"
            )
            return

        # Serializar requests al mismo IP del coordinador
        semaphore = await self._get_ip_semaphore(coordinator_tracker.host)
        async with semaphore:
            try:
                req = Request(
                    controller="Cluster",
                    command="update",
                    func="heartbeat",
                    args={
                        "tracker_id": self.cluster_state.tracker_id,
                        "query_count": self.cluster_state.query_count,
                        "vector_clock": self.cluster_state.vector_clock,
                    },
                )

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Enviando Heartbeat a {coordinator_tracker.tracker_id}..."
                )

                response = await self.request(
                    coordinator_tracker.host, coordinator_tracker.port, req
                )

                data = response.data if response and response.data else {}
                remote_is_coord = data.get("is_coordinator")
                remote_coord_id = data.get("coordinator_id")
                remote_coord_tracker_id = data.get("coordinator_tracker_id")

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Heartbeat a coordinador OK: remote_is_coord={remote_is_coord}, remote_coord={remote_coord_tracker_id}"
                )

                self._coordinator_heartbeat_fails = 0

                # CASO 2: CONFLICTO DE COORDINADORES (CHECK FIRST!)
                # El tracker al que le hacemos heartbeat se considera a sí mismo coordinador,
                # pero nosotros consideramos a alguien diferente como coordinador
                if (
                    remote_is_coord is True
                    and remote_coord_tracker_id
                    and remote_coord_tracker_id
                    != self.cluster_state.coordinator_tracker_id
                ):
                    logger.warning(
                        f"[{self.cluster_state.tracker_id}] CONFLICTO DE COORDINADORES: "
                        f"yo creo que es {self.cluster_state.coordinator_tracker_id}, "
                        f"pero {coordinator_tracker.tracker_id} dice que es {remote_coord_tracker_id}"
                    )
                    # Comparar Bully: quién debería ser coordinador
                    my_candidate = (
                        self.cluster_state.query_count,
                        self.cluster_state.coordinator_tracker_id,
                    )
                    remote_candidate = (
                        0,
                        remote_coord_tracker_id,
                    )  # Asumimos query_count=0 del otro coordinador

                    if remote_candidate > my_candidate:
                        logger.info(
                            f"[{self.cluster_state.tracker_id}] 🔄 RECONCILIACIÓN: "
                            f"Aceptando que {remote_coord_tracker_id} es mejor coordinador"
                        )
                        # Buscar el nuevo coordinador en caché
                        new_coord_tracker = (
                            await self.cluster_state.cache.get(remote_coord_id)
                            if remote_coord_id
                            else None
                        )
                        if new_coord_tracker:
                            self.cluster_state.coordinator_id = remote_coord_id
                            self.cluster_state.coordinator_tracker_id = (
                                new_coord_tracker.tracker_id
                            )
                            self.cluster_state.is_coordinator = False
                            logger.info(
                                f"[{self.cluster_state.tracker_id}] 🔔 COORDINADOR ACTUALIZADO: {self.cluster_state.coordinator_tracker_id}"
                            )
                    else:
                        logger.info(
                            f"[{self.cluster_state.tracker_id}] 🔄 RECONCILIACIÓN: "
                            f"Reafirmando que yo/mi coordinador {self.cluster_state.coordinator_tracker_id} es mejor"
                        )

                # CASO 1: El coordinador se considera a sí mismo coordinador (normal - después de verificar conflicto)
                elif remote_is_coord is True:
                    # Esperado: el coordinador se considera coordinador
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] Coordinador {remote_coord_tracker_id} confirmado"
                    )
                    pass

                # CASO 3: El coordinador reporta un cambio, actualizar
                elif remote_is_coord is False and remote_coord_id:
                    logger.info(
                        f"[{self.cluster_state.tracker_id}] Coordinador reporta nuevo líder: {remote_coord_tracker_id}"
                    )
                    # Buscar el nuevo coordinador en caché
                    new_coord_tracker = await self.cluster_state.cache.get(
                        remote_coord_id
                    )
                    if new_coord_tracker:
                        self.cluster_state.coordinator_id = remote_coord_id
                        self.cluster_state.coordinator_tracker_id = (
                            new_coord_tracker.tracker_id
                        )
                        self.cluster_state.is_coordinator = (
                            new_coord_tracker.tracker_id
                            == self.cluster_state.tracker_id
                        )
                        logger.info(
                            f"[{self.cluster_state.tracker_id}] 🔔 COORDINADOR ACTUALIZADO: {self.cluster_state.coordinator_tracker_id} | YO SOY COORDINADOR: {self.cluster_state.is_coordinator}"
                        )

            except Exception as e:
                self._coordinator_heartbeat_fails += 1
                logger.warning(
                    f"[{self.cluster_state.tracker_id}] Heartbeat al coordinador falló "
                    f"({self._coordinator_heartbeat_fails} veces): {e}"
                )

                if (
                    self._coordinator_heartbeat_fails
                    >= self.settings.heartbeat_fail_threshold
                ):
                    logger.info(
                        f"[{self.cluster_state.tracker_id}] Coordinador no responde, "
                        f"lanzando elección"
                    )
                    # Resetear coordinador para que no afecte la elección
                    self.cluster_state.coordinator_id = None
                    self.cluster_state.coordinator_tracker_id = None
                    self.cluster_state.is_coordinator = False

                    # Marcar cluster como inestable antes de la elección
                    self._last_coordinator_change = asyncio.get_event_loop().time()
                    self._cluster_stable = False
                    await self._trigger_election()
                    self._coordinator_heartbeat_fails = 0

    # ==================== Operaciones de Elección ====================

    async def _trigger_election(self):
        """Desencadena elección consultando a peers (no confía solo en caché)."""
        logger.info(f"[{self.cluster_state.tracker_id}] 🗳️ INICIANDO ELECCIÓN...")
        peers = self.get_cluster_view()
        logger.debug(
            f"[{self.cluster_state.tracker_id}] Peers en elección: {[p.tracker_id for p in peers]}"
        )

        # Mi estado local como candidato inicial
        local_tracker = TrackerState.model_validate(
            self.cluster_state, from_attributes=True
        )
        best_candidate = (local_tracker.query_count, local_tracker.tracker_id)
        best_id = local_tracker.tracker_id
        best_host = local_tracker.host

        # Si no hay peers, soy coordinador
        if not peers:
            logger.info(
                f"[{self.cluster_state.tracker_id}] No hay peers, soy coordinador por defecto"
            )
            self.cluster_state.is_coordinator = True
            self.cluster_state.coordinator_id = best_host
            self.cluster_state.coordinator_tracker_id = best_id
            return

        # Consultar a cada peer con RPC election en paralelo (similar a ping-sweep)
        semaphore = asyncio.Semaphore(self.settings.election_semaphore_size)

        async def _query_peer(peer: TrackerState):
            async with semaphore:
                return await self._send_election_request(
                    peer, best_id, best_candidate[0]
                )

        try:
            responses = await asyncio.wait_for(
                asyncio.gather(
                    *[_query_peer(peer) for peer in peers], return_exceptions=False
                ),
                timeout=self.settings.election_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[{self.cluster_state.tracker_id}] Timeout en elección, algunos peers no respondieron"
            )
            responses = []

        # Filtrar respuestas válidas (solo peers que respondieron)
        valid_responses = [resp for resp in responses if resp is not None]
        logger.debug(
            f"[{self.cluster_state.tracker_id}] Respuestas válidas: {len(valid_responses)}/{len(responses)}"
        )
        logger.info(
            f"[{self.cluster_state.tracker_id}] Candidatos: my_candidate={best_id}(qc={best_candidate[0]}), respuestas={[(r.candidate_id, r.query_count) for r in valid_responses]}"
        )

        # Invalidar del caché a peers que no respondieron (asumimos muertos)
        responded_ids = {r.candidate_id for r in valid_responses}
        for peer in peers:
            if peer.tracker_id not in responded_ids:
                # Remove non-responsive peer from cache
                await self.cluster_state.cache.invalidate(peer.host)
                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Invalidado del caché: {peer.tracker_id} (no respondió a elección)"
                )

        # Comparar contra respuestas válidas
        for resp in valid_responses:
            candidate_tuple = (resp.query_count, resp.candidate_id)
            logger.debug(
                f"[{self.cluster_state.tracker_id}] Response recibida: {resp.candidate_id} con query_count={resp.query_count}, best_candidate={best_candidate}"
            )
            if candidate_tuple > best_candidate:
                best_candidate = candidate_tuple
                best_id = resp.candidate_id
                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Nuevo mejor candidato: {best_id}"
                )
                # Buscar el host del nuevo best_id en las respuestas válidas (solo peers activos)
                for resp2 in valid_responses:
                    if resp2 and resp2.candidate_id == best_id:
                        # Obtener el host del peer original que respondió
                        for peer in peers:
                            if peer.tracker_id == best_id:
                                best_host = peer.host
                                break
                        break

        # Actualizar estado local con ganador
        was_coordinator = self.cluster_state.is_coordinator
        self.cluster_state.is_coordinator = best_id == self.cluster_state.tracker_id
        self.cluster_state.coordinator_id = best_host  # IP del coordinador
        self.cluster_state.coordinator_tracker_id = (
            best_id  # tracker_id del coordinador
        )

        logger.info(
            f"[{self.cluster_state.tracker_id}] 🔔 ELECCIÓN COMPLETADA: Nuevo coordinador = {best_id} | YO SOY COORDINADOR: {self.cluster_state.is_coordinator}"
        )

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

                # Descubrir peers NUEVOS (ya filtra contra cluster cache)
                ips = await self._discover_peers()

                if not ips:
                    continue

                logger.debug(
                    f"[{self.cluster_state.tracker_id}] Discovery encontró nuevos: {ips}"
                )

                # Enviar JOINs a todos los descubiertos (ya garantizado que son nuevos)
                for ip in ips:
                    host, port_str = ip.split(":", 1)
                    await self._send_join_request(host, int(port_str))

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

                # Actualizar estado de estabilidad
                if self._last_coordinator_change is not None:
                    time_since_change = (
                        asyncio.get_event_loop().time() - self._last_coordinator_change
                    )
                    if time_since_change >= self._stability_threshold:
                        if not self._cluster_stable:
                            self._cluster_stable = True
                            logger.info(
                                f"[{self.cluster_state.tracker_id}] ✅ Cluster ESTABLE (coordinador: {self.cluster_state.coordinator_tracker_id})"
                            )

                # No hacer heartbeat si el cluster está inestable (JOINs en progreso)
                if not self._cluster_stable:
                    logger.debug(
                        f"[{self.cluster_state.tracker_id}] Cluster inestable, skipping heartbeat"
                    )
                    continue

                # Si no hay coordinador, skip
                if not self.cluster_state.coordinator_id:
                    continue

                # Si yo soy el coordinador reportado, no me hago ping a mí mismo
                # PERO: si yo también pienso que soy coordinador Y el coordinador es alguien diferente,
                # aún debo hacer heartbeat para detectar conflictos y hacer Bully
                if (
                    self.cluster_state.is_coordinator
                    and self.cluster_state.coordinator_tracker_id
                    == self.cluster_state.tracker_id
                ):
                    # Yo soy el coordinador conocido por todos, no hago heartbeat
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
