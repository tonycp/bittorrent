"""
TorrentClient - Adaptador simplificado para la GUI.

Versión minimalista que usa bit_lib para funcionalidades básicas.
"""
import logging
import os
import hashlib
import json
import humanize
import asyncio
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

from ..config.config_mng import ConfigManager
from .tracker_manager import TrackerManager
from ..services.peer_service import PeerService

logger = logging.getLogger(__name__)


@dataclass
class ChunkInfo:
    """Información de un chunk"""
    chunk_id: int
    chunk_size: int
    display_size: str
    chunk_hash: str


@dataclass
class TorrentInfo:
    """Información de un archivo torrent"""
    file_hash: str
    file_name: str
    file_size: int
    chunk_size: int
    total_chunks: int
    display_size: str
    tracker_address: str = ""
    chunks_info: List[ChunkInfo] = None
    is_seeding: bool = False  # True si tenemos el archivo completo
    downloaded_chunks: int = 0  # Chunks descargados
    state: str = "queued"
    peers_total: int = 0
    download_rate: float = 0.0  # KB/s
    upload_rate: float = 0.0  # KB/s
    eta_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Inicializar chunks_info si es None"""
        if self.chunks_info is None:
            self.chunks_info = []
    
    @classmethod
    def from_torrent_file(cls, torrent_path: Path):
        """Carga info desde archivo .p2p"""
        logger.info(f"[FROM_FILE] Cargando torrent desde: {torrent_path}")
        
        if not torrent_path.exists():
            raise FileNotFoundError(f"Archivo torrent no encontrado: {torrent_path}")
        
        try:
            with open(torrent_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Archivo torrent corrupto o inválido: {e}")
        
        # Validar campos requeridos
        required = ["file_hash", "file_name", "file_size", "chunk_size", "total_chunks"]
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"Campos faltantes en torrent: {', '.join(missing)}")
        
        file_size = data["file_size"]
        logger.info(f"[FROM_FILE] file_size del JSON: {file_size} bytes ({humanize.naturalsize(file_size, binary=True)})")
        logger.info(f"[FROM_FILE] file_name: {data.get('file_name')}")
        logger.info(f"[FROM_FILE] total_chunks: {data.get('total_chunks')}")
        logger.info(f"[FROM_FILE] chunk_size: {data.get('chunk_size')}")
        
        # Cargar chunks_info si existe
        chunks_info = None
        if "chunks_info" in data:
            chunks_info = [ChunkInfo(**c) for c in data["chunks_info"]]
            logger.info(f"[FROM_FILE] Cargados {len(chunks_info)} chunks_info")
        
        torrent = cls(
            file_hash=data["file_hash"],
            file_name=data["file_name"],
            file_size=file_size,
            chunk_size=data["chunk_size"],
            total_chunks=data["total_chunks"],
            display_size=cls._format_size(file_size),
            tracker_address=data.get("tracker_address", ""),
            chunks_info=chunks_info,
            is_seeding=data.get("is_seeding", False),
            downloaded_chunks=data.get("downloaded_chunks", 0),
        )
        logger.info(f"[FROM_FILE] TorrentInfo creado - file_size: {torrent.file_size}, display_size: {torrent.display_size}")
        return torrent
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Formatea tamaño en bytes a string legible"""
        return humanize.naturalsize(size_bytes, binary=True)


@dataclass
class TorrentStatus:
    """Estado de un torrent (para GUI)"""
    file_name: str
    file_size: float
    downloaded_size: float
    progress: float
    total_chunks: float
    state: str = "queued"
    peers: int = 0
    download_rate: float = 0.0
    upload_rate: float = 0.0
    eta_seconds: Optional[float] = None


class TorrentClient:
    """
    Cliente BitTorrent simplificado para la GUI.
    
    Provee funcionalidades básicas sin dependencias complejas.
    """
    
    CHUNK_SIZE = 256 * 1024  # 256KB
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        
        # Torrents registrados (hash -> info)
        self._torrents: Dict[str, TorrentInfo] = {}
        
        # TrackerManager para announce/get_peers
        self.tracker_manager = TrackerManager(config_manager)
        
        # Peer ID realmente único para evitar colisiones entre contenedores
        listen_port = config_manager.get_listen_port()
        unique_suffix = uuid.uuid4().hex[:10]
        self.peer_id = f"peer-{socket.gethostname()}-{listen_port}-{unique_suffix}"
        
        # Estado
        self._initialized = False
        self._peer_server_started = False
        
        # Event loop persistente en thread separado (debe crearse ANTES de PeerService)
        self._loop = None
        self._loop_thread = None
        self._loop_ready = threading.Event()
        self._peer_server_future = None
        self._download_tasks: Dict[str, Any] = {}
        self._start_event_loop_thread()
        
        # PeerService para transferencia P2P de chunks (usa el loop creado)
        downloads_path = config_manager.get_download_path()
        listen_port = config_manager.get_listen_port()
        self.peer_service = PeerService(
            downloads_path=downloads_path,
            loop=self._loop,
            host="0.0.0.0",
            port=listen_port
        )

        self._last_upload_sample_ts = time.time()
        
        # Asegurar que existan los directorios
        self._ensure_directories()
    
    def _start_event_loop_thread(self):
        """Inicia un event loop persistente en un thread daemon"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        if not self._loop_ready.wait(timeout=2):
            logger.error("No se pudo inicializar el event loop del cliente")
    
    def _run_async_in_thread(self, coro):
        """Ejecuta corutina en el event loop del thread"""
        if not self._loop or not self._loop.is_running():
            logger.error("Event loop no está corriendo")
            return None
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        # Agregar callback para capturar excepciones
        def handle_result(fut):
            try:
                fut.result()
            except asyncio.CancelledError:
                logger.debug("Operación async cancelada")
            except Exception as e:
                logger.error(f"Error en operación async: {e}", exc_info=True)
        
        future.add_done_callback(handle_result)
        return future
    
    def _ensure_directories(self):
        """Crea directorios necesarios si no existen"""
        download_path = self.config.get_download_path()
        torrent_path = self.config.get_torrent_path()
        
        os.makedirs(download_path, exist_ok=True)
        os.makedirs(torrent_path, exist_ok=True)
    
    def setup_session(self):
        """Inicializa el cliente (llamado después de cambios de config)"""
        self._ensure_directories()
        self._initialized = True
        
        # Iniciar TrackerManager de forma asíncrona
        self._run_async_in_thread(self.tracker_manager.start())
        
        # Iniciar servidor P2P para servir chunks
        if not self._peer_server_started:
            self._peer_server_future = self._run_async_in_thread(self._start_peer_server())
            self._peer_server_started = True
        
        logger.info("Sesión de torrent iniciada")
    
    def get_torrent_info(self, torrent_path: str) -> TorrentInfo:
        """Carga información de un archivo .p2p"""
        return TorrentInfo.from_torrent_file(Path(torrent_path))
    
    def add_torrent(self, torrent_info: TorrentInfo) -> str:
        """Añade un torrent para descargar"""
        logger.info(f"[ADD_TORRENT] Agregando torrent: {torrent_info.file_name}")
        logger.info(f"[ADD_TORRENT] TorrentInfo recibido - file_size: {torrent_info.file_size}, total_chunks: {torrent_info.total_chunks}")

        # Añadir tracker específico del .p2p a la lista conocida (si existe)
        if torrent_info.tracker_address and ":" in torrent_info.tracker_address:
            try:
                tracker_host, tracker_port_str = torrent_info.tracker_address.rsplit(":", 1)
                tracker_host = tracker_host.strip()
                tracker_port = int(tracker_port_str)
                if tracker_host and 1 <= tracker_port <= 65535:
                    self.tracker_manager.prefer_tracker(tracker_host, tracker_port)
                    logger.info(f"[ADD_TORRENT] Tracker del torrent preferido: {tracker_host}:{tracker_port}")
            except Exception as e:
                logger.warning(f"[ADD_TORRENT] Tracker address inválido '{torrent_info.tracker_address}': {e}")
        
        if not self._initialized:
            self.setup_session()
        
        # Verificar si ya tenemos el archivo completo en downloads
        download_path = self.config.get_download_path()
        file_path = os.path.join(download_path, torrent_info.file_name)
        logger.info(f"[ADD_TORRENT] Verificando archivo en: {file_path}")
        
        if os.path.exists(file_path):
            file_size_disk = os.path.getsize(file_path)
            logger.info(f"[ADD_TORRENT] Archivo existe en disco, tamaño: {file_size_disk} bytes")
            
            # Verificar que el hash coincida
            actual_hash = self._calculate_file_hash(file_path)
            logger.info(f"[ADD_TORRENT] Hash calculado: {actual_hash[:16]}...")
            logger.info(f"[ADD_TORRENT] Hash esperado: {torrent_info.file_hash[:16]}...")
            
            if actual_hash == torrent_info.file_hash:
                # Ya tenemos el archivo completo
                torrent_info.is_seeding = True
                torrent_info.downloaded_chunks = torrent_info.total_chunks
                torrent_info.state = "seeding"
                logger.info("[ADD_TORRENT] ✓ Hash coincide - marcando como completo (seeding)")
                
                # Registrar archivo para seeding P2P
                self.peer_service.register_file(torrent_info.file_hash, file_path)
            else:
                logger.warning(f"[ADD_TORRENT] ✗ Hash NO coincide para {torrent_info.file_name}")
                torrent_info.is_seeding = False
                torrent_info.downloaded_chunks = 0
                torrent_info.state = "queued"
        else:
            # Archivo no existe, se debe descargar
            torrent_info.is_seeding = False
            torrent_info.downloaded_chunks = 0
            torrent_info.state = "queued"
            logger.info("[ADD_TORRENT] Archivo NO existe - se debe descargar")
        
        self._torrents[torrent_info.file_hash] = torrent_info
        logger.info(f"[ADD_TORRENT] Estado final - is_seeding: {torrent_info.is_seeding}, downloaded_chunks: {torrent_info.downloaded_chunks}/{torrent_info.total_chunks}")
        
        # Anunciar al tracker
        self._run_async_in_thread(self._announce_torrent(torrent_info))
        
        # Auto-iniciar descarga si el archivo no está completo
        if not torrent_info.is_seeding:
            logger.info(f"[ADD_TORRENT] Auto-iniciando descarga de {torrent_info.file_name}")
            self._start_download_task(torrent_info.file_hash)
        
        return torrent_info.file_hash
    
    async def _announce_torrent(self, torrent_info: TorrentInfo):
        """Anuncia este peer para un torrent (async)"""
        try:
            left = 0 if torrent_info.is_seeding else torrent_info.file_size
            
            await self.tracker_manager.announce_async(
                info_hash=torrent_info.file_hash,
                peer_id=self.peer_id,
                uploaded=0,
                downloaded=torrent_info.downloaded_chunks * torrent_info.chunk_size,
                left=left,
            )
            logger.info(f"[ANNOUNCE] Peer anunciado para torrent {torrent_info.file_hash[:16]}... (left={left})")
            
        except Exception as e:
            logger.error(f"[ANNOUNCE] Error: {e}", exc_info=True)
    
    def pause_torrent(self, torrent_handle: str):
        """Pausa un torrent"""
        torrent_info = self._torrents.get(torrent_handle)
        if not torrent_info:
            logger.error(f"Torrent {torrent_handle[:8]} no encontrado")
            return

        future = self._download_tasks.get(torrent_handle)
        if future and not future.done():
            future.cancel()

        torrent_info.state = "paused"
        torrent_info.download_rate = 0.0
        torrent_info.eta_seconds = None
        logger.info(f"Pausa de torrent: {torrent_handle[:8]}")
    
    def resume_torrent(self, torrent_handle: str):
        """Reanuda/inicia descarga de un torrent"""
        logger.info(f"Reanudación de torrent: {torrent_handle[:8]}")
        
        if torrent_handle not in self._torrents:
            logger.error(f"Torrent {torrent_handle[:8]} no encontrado")
            return
        
        torrent_info = self._torrents[torrent_handle]
        
        # Si ya está completo, no hacer nada
        if torrent_info.is_seeding:
            logger.info(f"Torrent {torrent_handle[:8]} ya está completo (seeding)")
            return
        
        # Iniciar descarga en el event loop
        logger.info(f"[RESUME] Iniciando descarga de {torrent_info.file_name}")
        torrent_info.state = "downloading"
        self._start_download_task(torrent_handle)

    def _start_download_task(self, torrent_hash: str):
        """Inicia descarga si no hay tarea activa para el torrent"""
        current = self._download_tasks.get(torrent_hash)
        if current and not current.done():
            logger.debug(f"[DOWNLOAD] Ya existe tarea activa para {torrent_hash[:8]}")
            return

        future = self._run_async_in_thread(self._download_torrent(torrent_hash))
        if future:
            self._download_tasks[torrent_hash] = future
    
    def remove_torrent(self, torrent_handle: str):
        """Elimina un torrent"""
        task = self._download_tasks.pop(torrent_handle, None)
        if task and not task.done():
            task.cancel()

        if torrent_handle in self._torrents:
            del self._torrents[torrent_handle]
            logger.info(f"Torrent eliminado: {torrent_handle[:8]}")
    
    def get_all_torrents(self) -> List[str]:
        """Obtiene lista de handles de todos los torrents"""
        self._refresh_upload_rates()
        return list(self._torrents.keys())

    def _refresh_upload_rates(self) -> None:
        """Actualiza upload_rate (KB/s) a partir de chunks servidos por PeerService."""
        now = time.time()
        elapsed = max(now - self._last_upload_sample_ts, 0.001)
        self._last_upload_sample_ts = now

        uploaded_by_torrent = self.peer_service.consume_uploaded_bytes_by_torrent()
        requester_counts = self.peer_service.get_active_requester_counts_by_torrent()

        for torrent in self._torrents.values():
            torrent.upload_rate = 0.0

        for torrent_hash, torrent in self._torrents.items():
            requester_count = requester_counts.get(torrent_hash, 0)
            if torrent.is_seeding:
                torrent.peers_total = requester_count
                if requester_count > 0:
                    logger.debug(f"[STATS] Seeder {torrent.file_name}: {requester_count} active peers requesting chunks")
            elif requester_count > 0:
                torrent.peers_total = max(torrent.peers_total, requester_count)
                logger.debug(f"[STATS] Downloader {torrent.file_name}: {requester_count} active requesters, {torrent.peers_total} total peers")

            uploaded_bytes = uploaded_by_torrent.get(torrent_hash, 0)
            if uploaded_bytes > 0:
                torrent.upload_rate = (uploaded_bytes / elapsed) / 1024

    def _filter_self_from_peers(self, peers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Elimina este cliente de la lista de peers para evitar auto-conexiones."""
        listen_port = self.config.get_listen_port()
        local_ips = {"127.0.0.1", "localhost", "0.0.0.0"}
        try:
            resolved = socket.gethostbyname(socket.gethostname())
            if resolved and not resolved.startswith("127.") and resolved != "0.0.0.0":
                local_ips.add(resolved)
        except Exception:
            pass

        try:
            announced_ip = self.tracker_manager._get_client_ip()
            if announced_ip and not announced_ip.startswith("127.") and announced_ip != "0.0.0.0":
                local_ips.add(announced_ip)
        except Exception:
            pass

        filtered: List[Dict[str, Any]] = []
        removed_by_endpoint = 0
        kept_same_peer_id = 0
        for peer in peers:
            peer_id = peer.get("peer_id")
            peer_ip = str(peer.get("ip", "")).strip()
            peer_port = peer.get("port")

            is_same_peer_id = bool(peer_id) and peer_id == self.peer_id
            is_local_endpoint = (
                isinstance(peer_port, int)
                and peer_port == listen_port
                and peer_ip in local_ips
            )

            # Filtrar SOLO por endpoint local real.
            # No filtrar solo por peer_id para evitar falsos positivos por colisiones/bugs de tracker.
            if is_local_endpoint:
                removed_by_endpoint += 1
                continue

            if is_same_peer_id:
                kept_same_peer_id += 1

            filtered.append(peer)

        if peers and (removed_by_endpoint > 0 or kept_same_peer_id > 0):
            logger.info(
                f"[PEERS] Filtrados endpoint local={removed_by_endpoint}, "
                f"peer_id_igual_conservados={kept_same_peer_id}, "
                f"recibidos={len(peers)}, quedan={len(filtered)}"
            )

        return filtered
    
    def get_status(self, torrent_handle: str) -> TorrentStatus:
        """Obtiene estado de un torrent"""
        torrent = self._torrents.get(torrent_handle)
        if not torrent:
            logger.warning(f"[GET_STATUS] Torrent no encontrado: {torrent_handle[:16]}...")
            return TorrentStatus(
                file_name="Unknown",
                file_size=0,
                downloaded_size=0,
                progress=0,
                total_chunks=0,
                state="error",
            )
        
        logger.debug(f"[GET_STATUS] Torrent: {torrent.file_name}")
        logger.debug(f"[GET_STATUS] file_size: {torrent.file_size} bytes, total_chunks: {torrent.total_chunks}")
        logger.debug(f"[GET_STATUS] is_seeding: {torrent.is_seeding}, downloaded_chunks: {torrent.downloaded_chunks}")
        
        # Calcular progreso real
        if torrent.is_seeding:
            progress = 100.0
            downloaded_bytes = torrent.file_size  # Bytes
            logger.debug(f"[GET_STATUS] SEEDING - progress: {progress}%, downloaded: {downloaded_bytes} bytes")
        else:
            progress = (torrent.downloaded_chunks / torrent.total_chunks * 100) if torrent.total_chunks > 0 else 0
            downloaded_bytes = torrent.downloaded_chunks * torrent.chunk_size  # Bytes
            logger.debug(f"[GET_STATUS] DOWNLOADING - progress: {progress:.1f}%, downloaded: {downloaded_bytes} bytes")
        
        logger.debug(f"[GET_STATUS] Retornando - file_size: {torrent.file_size} bytes, downloaded: {downloaded_bytes} bytes, progress: {progress:.1f}%")
        
        return TorrentStatus(
            file_name=torrent.file_name,
            file_size=torrent.file_size,  # Bytes
            downloaded_size=downloaded_bytes,  # Bytes
            progress=progress,
            total_chunks=torrent.total_chunks,
            state=torrent.state,
            peers=torrent.peers_total,
            download_rate=torrent.download_rate,
            upload_rate=torrent.upload_rate,
            eta_seconds=torrent.eta_seconds,
        )
    
    def create_torrent_file(self, file_path: str, address: Tuple[str, int]) -> Tuple[str, TorrentInfo]:
        """
        Crea un archivo .p2p desde un archivo local.
        
        Args:
            file_path: Ruta al archivo a compartir
            address: Tupla (ip, puerto) del tracker
        
        Returns:
            Tupla (ruta_archivo_torrent, TorrentInfo)
        """
        if not self._initialized:
            self.setup_session()
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        # Calcular hash y metadata
        file_size = os.path.getsize(file_path)
        file_hash = self._calculate_file_hash(file_path)
        file_name = os.path.basename(file_path)
        total_chunks = (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
        
        logger.info(f"[CREATE_TORRENT] Creando torrent para: {file_name}")
        logger.info(f"[CREATE_TORRENT] file_size: {file_size} bytes ({humanize.naturalsize(file_size, binary=True)})")
        logger.info(f"[CREATE_TORRENT] total_chunks: {total_chunks}")
        logger.info(f"[CREATE_TORRENT] chunk_size: {self.CHUNK_SIZE}")
        
        # Generar información de chunks
        chunks_info = []
        with open(file_path, "rb") as f:
            for i in range(total_chunks):
                chunk_data = f.read(self.CHUNK_SIZE)
                chunk_hash = self._calculate_chunk_hash(chunk_data)
                info = ChunkInfo(
                    chunk_id=i,
                    chunk_size=len(chunk_data),
                    display_size=humanize.naturalsize(len(chunk_data), binary=True),
                    chunk_hash=chunk_hash,
                )
                chunks_info.append(info)
        
        tracker_str = f"{address[0]}:{address[1]}"
        torrent_info = TorrentInfo(
            file_name=file_name,
            file_size=file_size,
            display_size=humanize.naturalsize(file_size, binary=True),
            file_hash=file_hash,
            chunk_size=self.CHUNK_SIZE,
            total_chunks=total_chunks,
            tracker_address=tracker_str,
            chunks_info=chunks_info,
            is_seeding=True,  # Tenemos el archivo completo
            downloaded_chunks=total_chunks,  # Todos los chunks disponibles
            state="seeding",
        )
        
        # Guardar archivo .p2p
        torrent_path = self.config.get_torrent_path()
        torrent_file = os.path.join(torrent_path, f"{file_name}.p2p")
        
        # Convertir a dict manualmente para evitar problemas con nested dataclasses
        torrent_dict = {
            "file_name": torrent_info.file_name,
            "file_size": torrent_info.file_size,
            "display_size": torrent_info.display_size,
            "file_hash": torrent_info.file_hash,
            "chunk_size": torrent_info.chunk_size,
            "total_chunks": torrent_info.total_chunks,
            "tracker_address": torrent_info.tracker_address,
            "is_seeding": torrent_info.is_seeding,
            "downloaded_chunks": torrent_info.downloaded_chunks,
            "chunks_info": [asdict(c) for c in chunks_info] if chunks_info else []
        }
        
        with open(torrent_file, "w") as f:
            json.dump(torrent_dict, f, indent=2)
        
        # SIEMPRE copiar archivo original a downloads para tener una única lógica
        download_path = self.config.get_download_path()
        dest_file = os.path.join(download_path, file_name)
        
        # Si el archivo no viene de downloads, copiarlo
        if os.path.abspath(file_path) != os.path.abspath(dest_file):
            import shutil
            os.makedirs(download_path, exist_ok=True)
            shutil.copy2(file_path, dest_file)
            logger.info(f"Archivo copiado a downloads: {dest_file}")
        
        # Agregar a torrents activos
        self._torrents[file_hash] = torrent_info
        
        # Registrar archivo para seeding P2P
        self.peer_service.register_file(file_hash, dest_file)
        
        # Registrar y anunciar al tracker de forma asíncrona
        self._run_async_in_thread(self._register_and_announce_torrent(file_hash, torrent_info))
        
        logger.info(f"Torrent creado: {torrent_file}")
        return torrent_file, torrent_info
    
    async def _register_and_announce_torrent(self, file_hash: str, torrent_info: TorrentInfo):
        """Registra torrent en tracker y anuncia este peer (async)"""
        try:
            # Registrar torrent
            success = await self.tracker_manager.register_torrent_async(
                torrent_hash=file_hash,
                file_name=torrent_info.file_name,
                file_size=torrent_info.file_size,
                total_chunks=torrent_info.total_chunks,
                piece_length=self.CHUNK_SIZE,
            )
            
            if success:
                logger.info(f"[REGISTER] Torrent {file_hash[:16]}... registrado en tracker")
            else:
                logger.warning(f"[REGISTER] No se pudo registrar torrent {file_hash[:16]}...")
            
            # Anunciar este peer (left=0 porque tenemos el archivo completo)
            await self.tracker_manager.announce_async(
                info_hash=file_hash,
                peer_id=self.peer_id,
                uploaded=0,
                downloaded=torrent_info.file_size,
                left=0 if torrent_info.is_seeding else torrent_info.file_size,
            )
            logger.info(f"[ANNOUNCE] Peer anunciado para torrent {file_hash[:16]}...")
            
        except Exception as e:
            logger.error(f"[REGISTER/ANNOUNCE] Error: {e}", exc_info=True)
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calcula SHA256 del archivo completo"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(256 * 1024):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    @staticmethod
    def _calculate_chunk_hash(data: bytes) -> str:
        """Calcula SHA256 de un chunk"""
        return hashlib.sha256(data).hexdigest()
    
    def connect_to_peer(self, host: str, port: int) -> bool:
        """
        Conecta manualmente a un peer (placeholder).
        """
        logger.info(f"Conexión manual a peer {host}:{port} (no implementado)")
        return True
    
    # ==================== P2P Server ====================
    
    async def _start_peer_server(self):
        """Inicia servidor P2P para servir chunks a otros peers"""
        try:
            listen_port = self.config.get_listen_port()
            
            logger.info(f"Iniciando servidor P2P en puerto {listen_port}...")
            
            # Crear servidor usando el event loop actual
            loop = asyncio.get_event_loop()
            server = await loop.create_server(
                self.peer_service.factory,
                '0.0.0.0',
                listen_port
            )
            
            logger.info(f"✅ Servidor P2P escuchando en puerto {listen_port}")
            
            # Servidor corre indefinidamente
            async with server:
                await server.serve_forever()
                
        except Exception as e:
            logger.error(f"Error iniciando servidor P2P: {e}", exc_info=True)
    
    # ==================== P2P Download ====================
    
    async def _download_torrent(self, torrent_hash: str):
        """
        Lógica principal de descarga de un torrent.
        
        1. Obtener peers del tracker
        2. Determinar chunks faltantes
        3. Descargar chunks de peers (distribuyendo entre múltiples peers)
        4. Actualizar progreso y anunciar periódicamente
        5. Anunciar completado al tracker
        """
        try:
            torrent_info = self._torrents.get(torrent_hash)
            if not torrent_info:
                logger.error(f"Torrent {torrent_hash[:8]} no encontrado")
                return

            torrent_info.state = "downloading"
            torrent_info.eta_seconds = None
            
            logger.info(f"[DOWNLOAD] Iniciando descarga de {torrent_info.file_name}")

            # Priorizar tracker del .p2p para este torrent
            if torrent_info.tracker_address and ":" in torrent_info.tracker_address:
                try:
                    tracker_host, tracker_port_str = torrent_info.tracker_address.rsplit(":", 1)
                    tracker_host = tracker_host.strip()
                    tracker_port = int(tracker_port_str)
                    if tracker_host and 1 <= tracker_port <= 65535:
                        self.tracker_manager.prefer_tracker(tracker_host, tracker_port)
                except Exception:
                    pass
            
            # 1. Obtener peers del tracker
            peers = await self.tracker_manager.get_peers_async(torrent_hash)
            peers = self._filter_self_from_peers(peers)
            torrent_info.peers_total = len(peers)
            
            if not peers:
                torrent_info.state = "stalled"
                logger.warning(f"[DOWNLOAD] No hay peers iniciales para {torrent_hash[:8]} - se seguirá intentando")
            
            logger.info(f"[DOWNLOAD] {len(peers)} peers disponibles")
            
            # 2. Determinar chunks faltantes
            missing_chunks = list(range(torrent_info.total_chunks))
            if torrent_info.downloaded_chunks > 0:
                # TODO: tracking real de chunks descargados
                missing_chunks = missing_chunks[torrent_info.downloaded_chunks:]
            
            logger.info(f"[DOWNLOAD] {len(missing_chunks)} chunks por descargar")
            
            # 3. Crear archivo si no existe
            download_path = self.config.get_download_path()
            file_path = os.path.join(download_path, torrent_info.file_name)
            
            if not os.path.exists(file_path):
                # Crear archivo vacío del tamaño correcto
                with open(file_path, 'wb') as f:
                    f.seek(torrent_info.file_size - 1)
                    f.write(b'\0')
                logger.info(f"[DOWNLOAD] Archivo creado: {file_path}")
            
            # Registrar archivo para permitir servir chunks ya descargados
            # Esto permite que otros peers descarguen de nosotros DURANTE la descarga
            self.peer_service.register_file(torrent_hash, file_path)
            
            # 4. Descargar chunks en paralelo
            initial_downloaded_chunks = torrent_info.downloaded_chunks
            downloaded = 0
            session_downloaded_bytes = 0
            last_announce_time = 0
            ANNOUNCE_INTERVAL = 30  # Anunciar cada 30 segundos
            ANNOUNCE_CHUNK_INTERVAL = 5  # O cada 5 chunks
            
            import time
            
            start_time = time.time()
            failed_peers = {}  # Track peers con fallos: {(ip, port): failure_count}
            pending_chunks = asyncio.Queue()  # ✅ Cambiar a Queue para workers persistentes
            
            # Añadir chunks iniciales
            for idx in missing_chunks:
                await pending_chunks.put(idx)
            
            stats_lock = threading.Lock()
            
            MAX_PARALLEL_DOWNLOADS = 4  # Descargar max 4 chunks en paralelo
            MAX_PEER_FAILURES = 5  # Remover peer después de N fallos
            last_peers_check = time.time()
            consecutive_no_progress = 0
            MAX_NO_PROGRESS_CYCLES = 30
            PEERS_CHECK_INTERVAL_WITH_PEERS = 20
            PEERS_CHECK_INTERVAL_NO_PEERS = 3
            download_complete = False
            
            async def check_peer_alive(peer_ip: str, peer_port: int, timeout: float = 5.0) -> bool:
                """Valida si un peer está respondiendo con un test simple"""
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(peer_ip, peer_port),
                        timeout=timeout
                    )
                    writer.close()
                    await writer.wait_closed()
                    return True
                except Exception as e:
                    logger.debug(f"[HEALTH] Peer {peer_ip}:{peer_port} no responde: {str(e)[:40]}")
                    return False
            
            async def download_chunk_worker(worker_id: int):
                """Worker que descarga chunks de forma paralela - loop persistente"""
                nonlocal downloaded, session_downloaded_bytes, consecutive_no_progress, download_complete, peers
                
                peer_idx = worker_id % len(peers) if peers else 0  # Distribución de peers
                
                while not download_complete:
                    try:
                        # Esperar chunk con timeout para permitir shutdown
                        chunk_idx = await asyncio.wait_for(
                            pending_chunks.get(),
                            timeout=2.0
                        )
                        
                        # Sentinela para shutdown (None)
                        if chunk_idx is None:
                            break
                        
                    except asyncio.TimeoutError:
                        # Sin chunks disponibles - esperar a que haya peers
                        if not peers:
                            logger.debug(f"[DOWNLOAD] Worker {worker_id} en espera - sin peers disponibles")
                            await asyncio.sleep(2)
                        continue
                    
                    chunk_downloaded = False
                    attempts = 0
                    
                    # Intentar con diferentes peers en rotación
                    if not peers:
                        await pending_chunks.put(chunk_idx)
                        await asyncio.sleep(1)
                        continue
                    
                    peers_count = len(peers)
                    
                    while attempts < peers_count and not chunk_downloaded:
                        # ✅ Rotar por peers: cada worker intenta con un peer diferente
                        current_peer_idx = (peer_idx + attempts) % peers_count
                        if current_peer_idx >= len(peers):
                            break
                            
                        peer = peers[current_peer_idx]
                        peer_ip = peer.get('ip')
                        peer_port = peer.get('port')
                        peer_key = (peer_ip, peer_port)
                        
                        if not peer_ip or not peer_port:
                            attempts += 1
                            continue
                        
                        logger.debug(f"[DOWNLOAD] Worker {worker_id}: chunk {chunk_idx} desde {peer_ip}:{peer_port}")
                        
                        try:
                            # ✅ Validar que peer está vivo ANTES de intentar
                            if not await check_peer_alive(peer_ip, peer_port, timeout=3.0):
                                logger.debug(f"[DOWNLOAD] Peer {peer_ip}:{peer_port} no responde")
                                failed_peers[peer_key] = failed_peers.get(peer_key, 0) + 1
                                attempts += 1
                                continue
                            
                            # Intentar descargar chunk
                            chunk_data = await self.peer_service.request_chunk(
                                peer_host=peer_ip,
                                peer_port=peer_port,
                                torrent_hash=torrent_hash,
                                chunk_index=chunk_idx,
                                timeout=20.0
                            )
                            
                            if chunk_data:
                                # ✅ Éxito
                                await self._write_chunk(file_path, chunk_idx, chunk_data, torrent_info.chunk_size)
                                
                                with stats_lock:
                                    downloaded += 1
                                    session_downloaded_bytes += len(chunk_data)
                                    consecutive_no_progress = 0
                                
                                # Reducir fallos (peer funciona bien)
                                failed_peers[peer_key] = max(0, failed_peers.get(peer_key, 0) - 1)
                                chunk_downloaded = True
                                
                                logger.debug(
                                    f"[DOWNLOAD] ✅ Worker {worker_id}: chunk {chunk_idx} de {peer_ip}:{peer_port}"
                                )
                                break
                        except Exception as e:
                            logger.debug(f"[DOWNLOAD] Worker {worker_id}: {peer_ip}:{peer_port} error: {str(e)[:40]}")
                            failed_peers[peer_key] = failed_peers.get(peer_key, 0) + 1
                            attempts += 1
                    
                    # Remover peers que fallan demasiado
                    peers = [
                        p for p in peers
                        if failed_peers.get((p.get('ip'), p.get('port')), 0) < MAX_PEER_FAILURES
                    ]
                    
                    # Si no se descargó, devolver a cola
                    if not chunk_downloaded:
                        with stats_lock:
                            consecutive_no_progress += 1
                        
                        if peers:
                            await pending_chunks.put(chunk_idx)
                        else:
                            # Sin peers, esperar
                            await pending_chunks.put(chunk_idx)
                            await asyncio.sleep(2)
            
            async def monitor_and_download():
                """Monitorea el progreso y gestiona workers"""
                nonlocal consecutive_no_progress, downloaded, session_downloaded_bytes, last_peers_check, last_announce_time, peers, download_complete
                
                # Crear tasks de workers
                worker_tasks = [
                    asyncio.create_task(download_chunk_worker(i))
                    for i in range(MAX_PARALLEL_DOWNLOADS)
                ]
                
                while not download_complete:
                    # Actualizar peers periódicamente
                    current_time = time.time()
                    check_interval = PEERS_CHECK_INTERVAL_WITH_PEERS if peers else PEERS_CHECK_INTERVAL_NO_PEERS
                    if current_time - last_peers_check > check_interval:
                        if not peers:
                            logger.info("[DOWNLOAD] Buscando peers del tracker...")
                        
                        new_peers = await self.tracker_manager.get_peers_async(torrent_hash)
                        new_peers = self._filter_self_from_peers(new_peers)
                        
                        if new_peers:
                            old_peer_count = len(peers)
                            peers = new_peers
                            torrent_info.peers_total = len(peers)
                            
                            # Limpiar fallos de peers antiguos
                            failed_peers.clear()
                            
                            if old_peer_count == 0:
                                logger.info(f"[DOWNLOAD] ✅ Peers encontrados: {len(peers)}")
                            else:
                                logger.info(f"[DOWNLOAD] Peers actualizados: {old_peer_count} → {len(peers)}")
                        elif not peers:
                            logger.warning("[DOWNLOAD] Sin peers disponibles - esperando...")
                        
                        last_peers_check = current_time
                    
                    # Anunciar progreso si toca
                    current_time = time.time()
                    if downloaded > 0 and (
                        downloaded % ANNOUNCE_CHUNK_INTERVAL == 0 or
                        (current_time - last_announce_time) >= ANNOUNCE_INTERVAL
                    ):
                        bytes_downloaded = (initial_downloaded_chunks + downloaded) * torrent_info.chunk_size
                        bytes_left = max(torrent_info.file_size - bytes_downloaded, 0)
                        
                        await self.tracker_manager.announce_async(
                            info_hash=torrent_hash,
                            peer_id=self.peer_id,
                            uploaded=0,
                            downloaded=bytes_downloaded,
                            left=bytes_left
                        )
                        last_announce_time = current_time
                    
                    # Actualizar estadísticas
                    with stats_lock:
                        torrent_info.downloaded_chunks = initial_downloaded_chunks + downloaded
                        torrent_info.state = "downloading" if peers else "stalled"
                        
                        elapsed = max(time.time() - start_time, 0.001)
                        rate_bps = session_downloaded_bytes / elapsed
                        torrent_info.download_rate = rate_bps / 1024
                        
                        downloaded_total_bytes = (initial_downloaded_chunks + downloaded) * torrent_info.chunk_size
                        remaining_bytes = max(torrent_info.file_size - downloaded_total_bytes, 0)
                        torrent_info.eta_seconds = (remaining_bytes / rate_bps) if rate_bps > 0 else None
                        
                        # Imprimir progreso cada 50 chunks
                        if downloaded > 0 and downloaded % 50 == 0:
                            progress = (downloaded / len(missing_chunks)) * 100
                            logger.info(
                                f"[DOWNLOAD] Progreso: {downloaded}/{len(missing_chunks)} ({progress:.1f}%) - "
                                f"Pendientes: {pending_chunks.qsize()} - Rate: {torrent_info.download_rate:.1f} KB/s"
                            )
                        
                        # Verificar si descarga está completa
                        if downloaded >= len(missing_chunks):
                            download_complete = True
                            logger.info(f"[DOWNLOAD] ✅ Descarga completa: {downloaded}/{len(missing_chunks)} chunks")
                    
                    # Si no hay progreso por bastante tiempo, buscar nuevos peers
                    if consecutive_no_progress >= MAX_NO_PROGRESS_CYCLES and peers:
                        logger.warning("[DOWNLOAD] Sin progreso hace bastante tiempo...")
                        consecutive_no_progress = 0
                        last_peers_check = current_time - 25  # Forzar siguiente actualización de peers
                    
                    # Dar tiempo a los workers
                    await asyncio.sleep(1)
                
                # Enviar sentinelas para shutdown de workers
                for _ in range(MAX_PARALLEL_DOWNLOADS):
                    await pending_chunks.put(None)
                
                # Esperar a que terminen todos los workers
                await asyncio.gather(*worker_tasks, return_exceptions=True)
            
            # Ejecutar monitoreo y descargas
            await monitor_and_download()
            
            # 5. Verificar si está completo
            with stats_lock:
                final_downloaded = downloaded
            
            if download_complete:
                # ✅ Todos los chunks fueron descargados
                torrent_info.is_seeding = True
                torrent_info.downloaded_chunks = torrent_info.total_chunks
                torrent_info.state = "completed"
                torrent_info.download_rate = 0.0
                torrent_info.eta_seconds = 0.0
                
                logger.info(f"✅ [DOWNLOAD] Descarga completa: {torrent_info.file_name} ({final_downloaded}/{len(missing_chunks)} chunks)")
                
                # Anunciar completado al tracker (event=completed)
                await self.tracker_manager.announce_async(
                    info_hash=torrent_hash,
                    peer_id=self.peer_id,
                    uploaded=0,
                    downloaded=torrent_info.file_size,
                    left=0
                )
            else:
                # Descarga incompleta - pero con guardado de chunks para futuros reintentos
                if torrent_info.state != "paused":
                    torrent_info.state = "paused"
                logger.warning(
                    f"[DOWNLOAD] Descarga pausada: {final_downloaded}/{len(missing_chunks)} chunks completados. "
                    f"Los chunks se mantienen guardados, se reanudarán cuando haya peers disponibles."
                )
        except asyncio.CancelledError:
            torrent_info = self._torrents.get(torrent_hash)
            if torrent_info and not torrent_info.is_seeding:
                torrent_info.state = "paused"
                torrent_info.download_rate = 0.0
                torrent_info.eta_seconds = None
            logger.info(f"[DOWNLOAD] Descarga cancelada: {torrent_hash[:8]}")
        except Exception as e:
            torrent_info = self._torrents.get(torrent_hash)
            if torrent_info:
                torrent_info.state = "error"
                torrent_info.download_rate = 0.0
                torrent_info.eta_seconds = None
            logger.error(f"[DOWNLOAD] Error en descarga: {e}", exc_info=True)
    
    async def _write_chunk(self, file_path: str, chunk_idx: int, chunk_data: bytes, chunk_size: int):
        """Escribe un chunk al archivo"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._write_chunk_sync,
                file_path,
                chunk_idx,
                chunk_data,
                chunk_size
            )
        except Exception as e:
            logger.error(f"Error escribiendo chunk {chunk_idx}: {e}")
            raise
    
    @staticmethod
    def _write_chunk_sync(file_path: str, chunk_idx: int, chunk_data: bytes, chunk_size: int):
        """Escribe chunk de forma síncrona (para executor)"""
        offset = chunk_idx * chunk_size
        with open(file_path, 'r+b') as f:
            f.seek(offset)
            f.write(chunk_data)
    
    def stop(self):
        """Detiene el cliente"""
        for torrent_hash, task in list(self._download_tasks.items()):
            if task and not task.done():
                task.cancel()
        self._download_tasks.clear()

        if self._peer_server_future and not self._peer_server_future.done():
            self._peer_server_future.cancel()

        if self._loop and self._loop.is_running():
            stop_future = self._run_async_in_thread(self.tracker_manager.stop())
            if stop_future:
                try:
                    stop_future.result(timeout=5)
                except Exception as e:
                    logger.warning(f"Error deteniendo TrackerManager: {e}")

            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5)

        self._initialized = False
        self._peer_server_started = False
        self._peer_server_future = None
        logger.info("TorrentClient detenido")
