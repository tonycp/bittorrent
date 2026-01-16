"""
TrackerClient - Cliente para comunicarse con trackers usando bit_lib
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any

from bit_lib.services import ClientService
from bit_lib.models import Request, Response

logger = logging.getLogger(__name__)


class TrackerClient(ClientService):
    """Cliente asíncrono para comunicación con trackers"""
    
    def __init__(self, **kwargs):
        """
        TrackerClient basado en bit_lib ClientService.
        No requiere host/port porque se conecta a trackers remotos.
        """
        super().__init__(**kwargs)
        self._running = False
    
    async def start(self):
        """Inicia el cliente (si necesita servidor de escucha)"""
        if not self._running:
            self._running = True
            # Por ahora solo cliente, no servidor
    
    async def stop(self):
        """Detiene el cliente"""
        self._running = False
    
    # ==================== Operaciones con Tracker ====================
    
    async def announce_peer(
        self,
        tracker_host: str,
        tracker_port: int,
        tracker_id: str,
        peer_id: str,
        torrent_hash: str,
        ip: str,
        port: int,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Anuncia un peer al tracker.
        
        Endpoint: Bit:create:announce
        """
        try:
            req = Request(
                controller="Bit",
                command="create",
                func="announce",
                args={
                    "info_hash": torrent_hash,
                    "peer_id": peer_id,
                    "ip": ip,
                    "port": port,
                    "left": left,
                    "event": "started" if uploaded == 0 and downloaded == 0 else None,
                }
            )
            
            response = await self.request(tracker_host, tracker_port, req, timeout=10)
            
            if response and response.data:
                logger.info(f"Announce exitoso a {tracker_host}:{tracker_port} para torrent {torrent_hash}")
                return response.data
            
            logger.warning(f"Announce falló a {tracker_host}:{tracker_port}")
            return None
            
        except Exception as e:
            logger.error(f"Error en announce: {e}")
            return None
    
    async def get_peers(
        self,
        tracker_host: str,
        tracker_port: int,
        torrent_hash: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene lista de peers para un torrent desde el tracker.
        Endpoint: Bit:get:peer_list
        """
        try:
            req = Request(
                controller="Bit",
                command="get",
                func="peer_list",
                args={
                    "info_hash": torrent_hash,
                }
            )
            
            response = await self.request(tracker_host, tracker_port, req, timeout=10)
            
            if response and response.data:
                # peer_list retorna {"info_hash", "total_active", "peers": [...]}
                data = response.data.get("data", response.data)
                peers = data.get("peers", [])
                logger.info(f"Obtenidos {len(peers)} peers para torrent {torrent_hash}")
                return peers
            
            return []
            
        except Exception as e:
            logger.error(f"Error obteniendo peers: {e}")
            return []
    
    async def stop_announce(
        self,
        tracker_host: str,
        tracker_port: int,
        tracker_id: str,
        peer_id: str,
        torrent_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Anuncia que el peer dejó de servir un torrent.
        
        Endpoint: Bit:create:announce con event="stopped"
        """
        try:
            req = Request(
                controller="Bit",
                command="create",
                func="announce",
                args={
                    "info_hash": torrent_hash,
                    "peer_id": peer_id,
                    "ip": "0.0.0.0",
                    "port": 0,
                    "left": 0,
                    "event": "stopped",
                }
            )
            
            response = await self.request(tracker_host, tracker_port, req, timeout=10)
            
            if response and response.data:
                logger.info(f"Stop announce exitoso para torrent {torrent_hash}")
                return response.data
            
            return None
            
        except Exception as e:
            logger.error(f"Error en stop announce: {e}")
            return None
    
    async def register_torrent(
        self,
        tracker_host: str,
        tracker_port: int,
        torrent_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
        piece_length: int = 16384,
    ) -> bool:
        """
        Registra un torrent nuevo en el tracker.
        Endpoint: Register:create:create_torrent
        """
        try:
            req = Request(
                controller="Register",
                command="create",
                func="create_torrent",
                args={
                    "info_hash": torrent_hash,
                    "file_name": file_name,
                    "file_size": file_size,
                    "total_chunks": total_chunks,
                    "piece_length": piece_length,
                }
            )
            
            response = await self.request(tracker_host, tracker_port, req, timeout=10)
            
            if response and response.data:
                status = response.data.get("status")
                logger.info(f"Torrent registrado: {torrent_hash} - status: {status}")
                return status == "ok" or status == "created"
            
            logger.warning(f"No response or no data: response={response}")
            return False
            
        except Exception as e:
            logger.error(f"Error registrando torrent: {e}", exc_info=True)
            return False
    
    # ==================== MessageService Abstract Methods ====================
    
    async def _handle_request(self, protocol, request: Request):
        """
        Maneja requests entrantes del tracker.
        TrackerClient normalmente no recibe requests (solo envía), 
        pero este método es requerido por la interfaz.
        """
        logger.warning(f"Received unexpected request from tracker: {request.command}")
        # Responder con error si es necesario
        return None
    
    async def _handle_binary(self, protocol, meta, data: bytes):
        """No recibimos datos binarios en cliente (por ahora)"""
        logger.warning("Binary data received but not expected in client")
    
    async def _on_connect(self, protocol):
        """Callback cuando se establece conexión"""
        logger.debug("Connection established to tracker")
    
    async def _on_disconnect(self, protocol, exc: Optional[Exception]):
        """Callback cuando se cierra conexión"""
        if exc:
            logger.debug(f"Connection closed with error: {exc}")
        else:
            logger.debug("Connection closed cleanly")
