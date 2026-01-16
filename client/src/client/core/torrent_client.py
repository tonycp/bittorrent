"""
TorrentClient - Adaptador entre GUI y ClientManager moderno.

Mantiene compatibilidad con la interfaz existente de la GUI
mientras usa la nueva arquitectura basada en bit_lib.
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..core.client_manager import ClientManager
from ..config.config_mng import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class TorrentInfo:
    """Información de un archivo torrent"""
    file_hash: str
    file_name: str
    file_size: int
    chunk_size: int
    total_chunks: int
    display_size: str
    
    @classmethod
    def from_torrent_file(cls, torrent_path: Path):
        """Carga info desde archivo .p2p"""
        # TODO: Implementar parser de archivo .p2p
        # Por ahora mock básico
        import json
        
        with open(torrent_path, 'r') as f:
            data = json.load(f)
        
        file_size = data.get("file_size", 0)
        
        return cls(
            file_hash=data.get("info_hash", ""),
            file_name=data.get("file_name", ""),
            file_size=file_size,
            chunk_size=data.get("chunk_size", 16384),
            total_chunks=data.get("total_chunks", 0),
            display_size=cls._format_size(file_size),
        )
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formatea tamaño en bytes a string legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


@dataclass
class TorrentStatus:
    """Estado de un torrent (para GUI)"""
    file_name: str
    file_size: float
    downloaded_size: float
    progress: float
    total_chunks: float
    peers: int = 0
    download_rate: float = 0.0
    upload_rate: float = 0.0


class TorrentClient:
    """
    Cliente BitTorrent que usa ClientManager moderno.
    
    Provee interfaz compatible con la GUI existente.
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        
        # Manager moderno (se crea en setup_session)
        self.client_manager: Optional[ClientManager] = None
        
        # Estado
        self._initialized = False
    
    def setup_session(self):
        """Inicializa el cliente (llamado después de cambios de config)"""
        if self._initialized and self.client_manager:
            # Reiniciar
            self.client_manager.stop()
        
        # Crear client manager
        self.client_manager = ClientManager(self.config)
        self.client_manager.start()
        
        self._initialized = True
        logger.info("Sesión de torrent iniciada")
    
    def get_torrent_info(self, torrent_path: str) -> TorrentInfo:
        """Carga información de un archivo .p2p"""
        return TorrentInfo.from_torrent_file(Path(torrent_path))
    
    def add_torrent(self, torrent_info: TorrentInfo) -> str:
        """Añade un torrent para descargar"""
        if not self._initialized:
            self.setup_session()
        
        return self.client_manager.add_torrent(
            torrent_hash=torrent_info.file_hash,
            file_name=torrent_info.file_name,
            file_size=torrent_info.file_size,
            chunk_size=torrent_info.chunk_size,
            total_chunks=torrent_info.total_chunks,
        )
    
    def pause_torrent(self, torrent_handle: str):
        """Pausa un torrent"""
        if self.client_manager:
            self.client_manager.pause_download(torrent_handle)
    
    def resume_torrent(self, torrent_handle: str):
        """Reanuda un torrent"""
        if self.client_manager:
            self.client_manager.start_download(torrent_handle)
    
    def remove_torrent(self, torrent_handle: str):
        """Elimina un torrent"""
        if self.client_manager:
            self.client_manager.remove_torrent(torrent_handle)
    
    def get_all_torrents(self) -> List[str]:
        """Obtiene lista de handles de todos los torrents"""
        if not self.client_manager:
            return []
        return self.client_manager.get_all_torrents()
    
    def get_status(self, torrent_handle: str) -> TorrentStatus:
        """Obtiene estado de un torrent"""
        if not self.client_manager:
            return TorrentStatus(
                file_name="Unknown",
                file_size=0,
                downloaded_size=0,
                progress=0,
                total_chunks=0,
            )
        
        status_dict = self.client_manager.get_torrent_status(torrent_handle)
        if not status_dict:
            return TorrentStatus(
                file_name="Unknown",
                file_size=0,
                downloaded_size=0,
                progress=0,
                total_chunks=0,
            )
        
        return TorrentStatus(
            file_name=status_dict.get("file_name", "Unknown"),
            file_size=status_dict.get("file_size", 0) / (1024 * 1024),  # MB
            downloaded_size=status_dict.get("downloaded", 0) / (1024 * 1024),  # MB
            progress=status_dict.get("progress", 0),
            total_chunks=status_dict.get("file_size", 0) / 16384,  # Estimado
            peers=status_dict.get("peers", 0),
        )
    
    def connect_to_peer(self, host: str, port: int) -> bool:
        """
        Conecta manualmente a un peer (para debug/testing).
        
        En la arquitectura moderna esto no es necesario,
        los peers se descubren automáticamente vía tracker.
        """
        logger.info(f"Conexión manual a peer {host}:{port} no necesaria en arquitectura moderna")
        return True
    
    def stop(self):
        """Detiene el cliente"""
        if self.client_manager:
            self.client_manager.stop()
            logger.info("TorrentClient detenido")
