import asyncio
import logging
import socket
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..config.utils import get_env_settings
from ..config.config_mng import ConfigManager
from ..connection.tracker_client import TrackerClient

logger = logging.getLogger(__name__)


class TrackerManager:
    """Manager para comunicación con trackers usando bit_lib"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.env_settings = get_env_settings()
        
        # Cliente asíncrono para trackers (bit_lib)
        self.tracker_client: Optional[TrackerClient] = None
        
        # Cache de trackers conocidos (para tolerancia a fallos)
        self._known_trackers: List[tuple] = []
        self._current_tracker_idx = 0
        
        # Tracker actual conectado (para GUI)
        self._current_tracker: Optional[tuple] = None
    
    @staticmethod
    def _get_client_ip() -> str:
        """Obtiene la IP del cliente"""
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"
    
    async def start(self):
        """Inicia el cliente de tracker (async)"""
        if not self.tracker_client:
            self.tracker_client = TrackerClient()
            await self.tracker_client.start()
            
            # Inicializar lista de trackers conocidos desde config
            tracker_host, tracker_port = self.config_manager.get_tracker_address()
            self._known_trackers = [(tracker_host, tracker_port)]
            self._current_tracker = (tracker_host, tracker_port)
            
            logger.info(f"TrackerManager iniciado (tracker principal: {tracker_host}:{tracker_port})")
    
    async def stop(self):
        """Detiene el cliente de tracker"""
        if self.tracker_client:
            await self.tracker_client.stop()
            logger.info("TrackerManager detenido")
    
    def get_current_tracker(self) -> Optional[tuple]:
        """Retorna el tracker actual conectado (host, port)"""
        return self._current_tracker
    
    def get_known_trackers(self) -> List[tuple]:
        """Retorna lista de trackers conocidos"""
        return self._known_trackers.copy()
    
    def add_tracker(self, host: str, port: int):
        """Añade un tracker a la lista de conocidos"""
        tracker_tuple = (host, port)
        if tracker_tuple not in self._known_trackers:
            self._known_trackers.append(tracker_tuple)
            logger.info(f"Tracker añadido: {host}:{port}")

    
    
    # ==================== Métodos Asíncronos (core) ====================
    
    async def register_torrent_async(
        self, 
        torrent_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
        piece_length: int = 16384,
    ) -> bool:
        """Registra torrent en tracker (async)"""
        if not self.tracker_client:
            await self.start()
        
        # Intentar con trackers conocidos hasta que uno funcione
        for tracker_host, tracker_port in self._known_trackers:
            try:
                success = await self.tracker_client.register_torrent(
                    tracker_host=tracker_host,
                    tracker_port=tracker_port,
                    torrent_hash=torrent_hash,
                    file_name=file_name,
                    file_size=file_size,
                    total_chunks=total_chunks,
                    piece_length=piece_length,
                )
                
                if success:
                    self._current_tracker = (tracker_host, tracker_port)
                    logger.info(f"Torrent {torrent_hash[:8]} registrado en {tracker_host}:{tracker_port}")
                    return True
            except Exception as e:
                logger.warning(f"Error registrando en tracker {tracker_host}:{tracker_port}: {e}")
                continue
        
        logger.error("No se pudo registrar el torrent en ningún tracker")
        return False
    
    async def get_peers_async(
        self, 
        info_hash: str
    ) -> List[Dict[str, Any]]:
        """Obtiene peers para un torrent (async)"""
        if not self.tracker_client:
            await self.start()
        
        # Intentar con trackers conocidos
        for tracker_host, tracker_port in self._known_trackers:
            try:
                peers = await self.tracker_client.get_peers(
                    tracker_host=tracker_host,
                    tracker_port=tracker_port,
                    torrent_hash=info_hash,
                )
                
                if peers:
                    self._current_tracker = (tracker_host, tracker_port)
                    logger.info(f"Obtenidos {len(peers)} peers de {tracker_host}:{tracker_port}")
                    return peers
            except Exception as e:
                logger.warning(f"Error obteniendo peers de {tracker_host}:{tracker_port}: {e}")
                continue
        
        logger.warning(f"No se pudieron obtener peers para {info_hash[:8]}")
        return []
    
    async def announce_async(
        self, 
        info_hash: str, 
        peer_id: str,
        uploaded: int = 0,
        downloaded: int = 0,
        left: int = 0
    ):
        """Anuncia peer al tracker (async)"""
        if not self.tracker_client:
            await self.start()
        
        tracker_host, tracker_port = self._known_trackers[self._current_tracker_idx]
        
        # Usar tracker_id basado en host:port
        tracker_id = f"{tracker_host}:{tracker_port}"
        
        try:
            await self.tracker_client.announce_peer(
                tracker_host=tracker_host,
                tracker_port=tracker_port,
                tracker_id=tracker_id,
                peer_id=peer_id,
                torrent_hash=info_hash,
                ip=self._get_client_ip(),
                port=self.config_manager.get_listen_port(),
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
            )
            
            self._current_tracker = (tracker_host, tracker_port)
            logger.info(f"Announce exitoso para {info_hash[:8]}")
        except Exception as e:
            logger.error(f"Error en announce: {e}")
            # Rotar al siguiente tracker
            self._current_tracker_idx = (self._current_tracker_idx + 1) % len(self._known_trackers)
    
    async def discover_trackers_async(self) -> List[tuple]:
        """
        Descubre trackers adicionales de la red (para tolerancia a fallos).
        
        En una implementación completa, esto podría usar:
        - DHT (Distributed Hash Table)
        - Tracker exchanges
        - Configuración estática
        """
        # Por ahora retornar trackers conocidos
        return self._known_trackers.copy()
    
    # ==================== Wrappers Síncronos (para compatibilidad) ====================
    
    def register_torrent(
        self, 
        torrent_data, 
        tracker_address=None
    ) -> bool:
        """Registra torrent (sync wrapper)"""
        return asyncio.run(self.register_torrent_async(
            torrent_hash=torrent_data.file_hash,
            file_name=torrent_data.file_name,
            file_size=torrent_data.file_size,
            total_chunks=torrent_data.total_chunks,
        ))
    
    def get_peers(self, info_hash: str, tracker_address=None) -> List[Dict[str, Any]]:
        """Obtiene peers (sync wrapper)"""
        return asyncio.run(self.get_peers_async(info_hash))
    
    def announce(self, info_hash: str, peer_id: str, tracker_address=None):
        """Anuncia peer (sync wrapper)"""
        asyncio.run(self.announce_async(info_hash, peer_id))

