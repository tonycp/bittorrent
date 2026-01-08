from typing import Dict, Iterable, TypeAlias, Optional
from dataclasses import dataclass
import asyncio
import logging

from bit_lib.services import UniqueService, ClientService, PingSweepDiscovery
from bit_lib.context import CacheManager
from bit_lib.models import (
    decode_request,
    process_header,
    EventSuccess,
    Request,
    Data,
)

from src.handlers import HandlerContainer, ReplicationHandler, EventHandler
from src.models.event import EventLog

RepHandler: TypeAlias = ReplicationHandler
logger = logging.getLogger(__name__)


@dataclass
class NeighborState:
    """Estado de replicación por vecino"""
    last_ts: int = 0
    retries: int = 0
    alive: bool = True


class ReplicationService(UniqueService, ClientService):
    def __init__(
        self,
        host: str,
        port: int,
        tracker_id: str,
        neighbors: list[Dict[str, str | int]],
        replication_interval: int = 2,
        heartbeat_interval: int = 5,
        timeout: float = 3.0,
        max_retries: int = 2,
        discovery_service: Optional[PingSweepDiscovery] = None,
    ):
        super().__init__(host, port, EventHandler.endpoint)
        
        self.tracker_id = tracker_id
        self.neighbors = neighbors
        self.replication_interval = replication_interval
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._discovery_service = discovery_service
        
        # Caché de estado de vecinos con TTL (actualiza cada replication_interval)
        self._neighbor_cache = CacheManager(
            default_ttl=replication_interval * 2,
            name="replication_neighbors"
        )
        
        # Tasks de los loops periódicos
        self._replication_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    def _neighbor_key(self, host: str, port: int) -> str:
        return f"{host}:{port}"

    def _init_neighbor_state(self):
        """Inicializa estado de vecinos en caché"""
        for neighbor in self.neighbors:
            key = self._neighbor_key(neighbor["host"], neighbor["port"])
            # no await: se siembra de forma best-effort (inicial), se usará get_or_fetch después
            self._neighbor_cache.set(key, NeighborState())

    async def _get_neighbor_state(self, key: str) -> NeighborState:
        """Obtiene estado del vecino desde caché, inicializa si no existe"""
        state = await self._neighbor_cache.get(key)
        if state is None:
            state = NeighborState()
            await self._neighbor_cache.set(key, state)
        return state

    async def _get_active_neighbors(self) -> list[Dict[str, str | int]]:
        """Obtiene lista de vecinos activos usando discovery o config estática"""
        if self._discovery_service:
            # Usa discovery para encontrar peers activos en la red
            # Asume subnet local /24 y puerto conocido
            subnet = f"{self.host.rsplit('.', 1)[0]}.0/24"
            alive_peers = await self._discovery_service.ping_range(
                subnet=subnet,
                port=self.port,
                timeout=self.timeout
            )
            return [{"host": host, "port": port} for host, port in alive_peers]
        else:
            # Fallback a configuración estática
            return self.neighbors

    async def register_with_neighbor(self, host: str, port: int) -> bool:
        """Registra este tracker con un vecino via RPC"""
        from src.handlers import EventHandler
        
        try:
            # Obtener vector clock actual
            event_hdl = EventHandler.endpoint
            vc = await event_hdl.get_current_vc(self.tracker_id)
            
            req = Request(
                controller="Tracker",
                command="create",
                func="register_tracker",
                data={
                    "tracker_id": self.tracker_id,
                    "host": self.host,
                    "port": self.port,
                    "status": "online",
                    "vector_clock": vc.to_dict(),
                },
            )
            
            response = await self.request(host, port, req, timeout=self.timeout)
            return response is not None
        
        except Exception as e:
            logger.warning(f"Failed to register with {host}:{port}: {e}")
            return False

    async def start_replication_loops(self):
        """Inicia los loops periódicos de replicación y heartbeat"""
        if self._running:
            return
        
        self._running = True
        self._init_neighbor_state()
        
        self._replication_task = asyncio.create_task(self._replication_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info(f"Replication loops started for tracker {self.tracker_id}")

    async def stop_replication_loops(self):
        """Detiene los loops periódicos"""
        self._running = False
        
        if self._replication_task:
            self._replication_task.cancel()
            try:
                await self._replication_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Replication loops stopped for tracker {self.tracker_id}")

    async def _replication_loop(self):
        """Loop que envía eventos pendientes a vecinos periódicamente"""
        from src.repos import RepoContainer
        
        while self._running:
            try:
                await asyncio.sleep(self.replication_interval)
                
                event_repo = RepoContainer.event_log_repo()
                
                # Obtener lista de vecinos
                neighbors_to_replicate = await self._get_active_neighbors()
                
                for neighbor in neighbors_to_replicate:
                    host, port = neighbor["host"], neighbor["port"]
                    key = self._neighbor_key(host, port)
                    state = await self._get_neighbor_state(key)
                    
                    if not state.alive:
                        continue
                    
                    # Obtener eventos pendientes desde último ts enviado
                    pending = await event_repo.get_pending_replication(state.last_ts)
                    
                    if not pending:
                        continue
                    
                    # Enviar lote de eventos
                    try:
                        events_data = [ev.model_dump() for ev in pending]
                        req = Request(
                            controller="Replication",
                            command="update",
                            func="replicate_events",
                            data={
                                "source_tracker_id": self.tracker_id,
                                "events": events_data,
                            },
                        )
                        
                        response = await self.request(host, port, req, timeout=self.timeout)
                        
                        if response:
                            # Actualizar last_ts al último evento enviado
                            state.last_ts = pending[-1].timestamp
                            state.retries = 0
                            await self._neighbor_cache.set(key, state)
                            logger.debug(f"Replicated {len(pending)} events to {key}")
                    
                    except Exception as e:
                        state.retries += 1
                        await self._neighbor_cache.set(key, state)
                        logger.warning(f"Failed to replicate to {key}: {e}")
                        
                        if state.retries >= self.max_retries:
                            state.alive = False
                            await self._neighbor_cache.set(key, state)
                            logger.error(f"Neighbor {key} marked as down after {self.max_retries} retries")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in replication loop: {e}")

    async def _heartbeat_loop(self):
        """Loop que envía heartbeats a vecinos periódicamente"""
        from src.repos import RepoContainer
        
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                event_repo = RepoContainer.event_log_repo()
                last_event = await event_repo.get_latest_by_tracker(self.tracker_id)
                last_ts = last_event.timestamp if last_event else 0
                
                # Obtener lista de vecinos activos
                neighbors_to_heartbeat = await self._get_active_neighbors()
                
                for neighbor in neighbors_to_heartbeat:
                    host, port = neighbor["host"], neighbor["port"]
                    key = self._neighbor_key(host, port)
                    state = await self._get_neighbor_state(key)
                    
                    try:
                        req = Request(
                            controller="Replication",
                            command="create",
                            func="heartbeat",
                            data={
                                "tracker_id": self.tracker_id,
                                "last_timestamp": last_ts,
                                "event_count": 0,  # TODO: contador real
                            },
                        )
                        
                        response = await self.request(host, port, req, timeout=self.timeout)
                        
                        if response and not state.alive:
                            # Vecino volvió a estar disponible
                            state.alive = True
                            state.retries = 0
                            await self._neighbor_cache.set(key, state)
                            logger.info(f"Neighbor {key} is alive again")
                    
                    except Exception as e:
                        logger.debug(f"Heartbeat failed for {key}: {e}")
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def send_event(self, host: str, port: int, event: EventLog) -> None:
        req = Request(
            controller=self.service_id,
            command="update",
            func=event.operation,
            data=event.model_dump(),
        )
        await self.request(host, port, req, timeout=3.0)

    async def send_events(self, host: str, port: int, events: Iterable) -> None:
        for ev in events:
            await self.send_event(host, port, ev)

    async def _dispatch_request(
        self,
        hdl_key: str,
        data: Data,
        msg_id: str,
    ):
        event_hdl = HandlerContainer.event_hdl()
        response = await event_hdl._exec_handler(hdl_key, data)

        if isinstance(response, EventSuccess):
            header, data = decode_request(response.request)
            _, hdl_key = process_header(header)

            handler = HandlerContainer.replication_hdl()
            return await handler.process(hdl_key, data, msg_id)
