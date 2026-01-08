from typing import Dict, Iterable, TypeAlias
import asyncio
import logging

from bit_lib.services import UniqueService, ClientService
from bit_lib.proto import BlockCollector, BlockCollectorCache
from bit_lib.models import (
    decode_request,
    process_header,
    EventSuccess,
    MetaData,
    Request,
    Data,
)

from src.handlers import HandlerContainer, ReplicationHandler, EventHandler
from src.models.event import EventLog

RepHandler: TypeAlias = ReplicationHandler
logger = logging.getLogger(__name__)


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
    ):
        super().__init__(host, port, EventHandler.endpoint)
        
        self.tracker_id = tracker_id
        self.neighbors = neighbors
        self.replication_interval = replication_interval
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Estado de replicación por vecino: {neighbor_key: {"last_ts": int, "retries": int, "alive": bool}}
        self._neighbor_state: Dict[str, Dict] = {}
        
        # Tasks de los loops periódicos
        self._replication_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    def _neighbor_key(self, host: str, port: int) -> str:
        return f"{host}:{port}"

    def _init_neighbor_state(self):
        """Inicializa estado de vecinos"""
        for neighbor in self.neighbors:
            key = self._neighbor_key(neighbor["host"], neighbor["port"])
            if key not in self._neighbor_state:
                self._neighbor_state[key] = {
                    "last_ts": 0,
                    "retries": 0,
                    "alive": True,
                }

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
                
                for neighbor in self.neighbors:
                    host, port = neighbor["host"], neighbor["port"]
                    key = self._neighbor_key(host, port)
                    state = self._neighbor_state[key]
                    
                    if not state["alive"]:
                        continue
                    
                    # Obtener eventos pendientes desde último ts enviado
                    pending = await event_repo.get_pending_replication(state["last_ts"])
                    
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
                            state["last_ts"] = pending[-1].timestamp
                            state["retries"] = 0
                            logger.debug(f"Replicated {len(pending)} events to {key}")
                    
                    except Exception as e:
                        state["retries"] += 1
                        logger.warning(f"Failed to replicate to {key}: {e}")
                        
                        if state["retries"] >= self.max_retries:
                            state["alive"] = False
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
                
                for neighbor in self.neighbors:
                    host, port = neighbor["host"], neighbor["port"]
                    key = self._neighbor_key(host, port)
                    state = self._neighbor_state[key]
                    
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
                        
                        if response and not state["alive"]:
                            # Vecino volvió a estar disponible
                            state["alive"] = True
                            state["retries"] = 0
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
