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
    peers: int = 0
    download_rate: float = 0.0
    upload_rate: float = 0.0


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
        
        # Peer ID único para este cliente
        self.peer_id = f"peer-{socket.gethostname()}-{os.getpid()}"
        
        # Estado
        self._initialized = False
        self._peer_server_started = False
        
        # Event loop persistente en thread separado (debe crearse ANTES de PeerService)
        self._loop = None
        self._loop_thread = None
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
        
        # Asegurar que existan los directorios
        self._ensure_directories()
    
    def _start_event_loop_thread(self):
        """Inicia un event loop persistente en un thread daemon"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # Esperar a que el loop esté listo
        import time
        time.sleep(0.1)
    
    def _run_async_in_thread(self, coro):
        """Ejecuta corutina en el event loop del thread"""
        if not self._loop or not self._loop.is_running():
            logger.error("Event loop no está corriendo")
            return
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        # Agregar callback para capturar excepciones
        def handle_result(fut):
            try:
                fut.result()
            except Exception as e:
                logger.error(f"Error en operación async: {e}", exc_info=True)
        
        future.add_done_callback(handle_result)
    
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
            self._run_async_in_thread(self._start_peer_server())
            self._peer_server_started = True
        
        logger.info("Sesión de torrent iniciada")
    
    def get_torrent_info(self, torrent_path: str) -> TorrentInfo:
        """Carga información de un archivo .p2p"""
        return TorrentInfo.from_torrent_file(Path(torrent_path))
    
    def add_torrent(self, torrent_info: TorrentInfo) -> str:
        """Añade un torrent para descargar"""
        logger.info(f"[ADD_TORRENT] Agregando torrent: {torrent_info.file_name}")
        logger.info(f"[ADD_TORRENT] TorrentInfo recibido - file_size: {torrent_info.file_size}, total_chunks: {torrent_info.total_chunks}")
        
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
                logger.info(f"[ADD_TORRENT] ✓ Hash coincide - marcando como completo (seeding)")
                
                # Registrar archivo para seeding P2P
                self.peer_service.register_file(torrent_info.file_hash, file_path)
            else:
                logger.warning(f"[ADD_TORRENT] ✗ Hash NO coincide para {torrent_info.file_name}")
                torrent_info.is_seeding = False
                torrent_info.downloaded_chunks = 0
        else:
            # Archivo no existe, se debe descargar
            torrent_info.is_seeding = False
            torrent_info.downloaded_chunks = 0
            logger.info(f"[ADD_TORRENT] Archivo NO existe - se debe descargar")
        
        self._torrents[torrent_info.file_hash] = torrent_info
        logger.info(f"[ADD_TORRENT] Estado final - is_seeding: {torrent_info.is_seeding}, downloaded_chunks: {torrent_info.downloaded_chunks}/{torrent_info.total_chunks}")
        
        # Anunciar al tracker
        self._run_async_in_thread(self._announce_torrent(torrent_info))
        
        # Auto-iniciar descarga si el archivo no está completo
        if not torrent_info.is_seeding:
            logger.info(f"[ADD_TORRENT] Auto-iniciando descarga de {torrent_info.file_name}")
            self._run_async_in_thread(self._download_torrent(torrent_info.file_hash))
        
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
        """Pausa un torrent (placeholder)"""
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
        self._run_async_in_thread(self._download_torrent(torrent_handle))
        
        if torrent_handle not in self._torrents:
            logger.error(f"Torrent {torrent_handle[:8]} no encontrado")
            return
        
        torrent_info = self._torrents[torrent_handle]
        
        # Si ya está completo, no hacer nada
        if torrent_info.is_seeding:
            logger.info(f"Torrent {torrent_handle[:8]} ya está completo (seeding)")
            return
        
        # Iniciar descarga en el event loop
        self._run_async_in_thread(self._download_torrent(torrent_handle))
    
    def remove_torrent(self, torrent_handle: str):
        """Elimina un torrent"""
        if torrent_handle in self._torrents:
            del self._torrents[torrent_handle]
            logger.info(f"Torrent eliminado: {torrent_handle[:8]}")
    
    def get_all_torrents(self) -> List[str]:
        """Obtiene lista de handles de todos los torrents"""
        return list(self._torrents.keys())
    
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
            peers=0,
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
        3. Descargar chunks de peers
        4. Actualizar progreso
        5. Anunciar al tracker
        """
        try:
            torrent_info = self._torrents.get(torrent_hash)
            if not torrent_info:
                logger.error(f"Torrent {torrent_hash[:8]} no encontrado")
                return
            
            logger.info(f"[DOWNLOAD] Iniciando descarga de {torrent_info.file_name}")
            
            # 1. Obtener peers del tracker
            peers = await self.tracker_manager.get_peers_async(torrent_hash)
            
            if not peers:
                logger.warning(f"[DOWNLOAD] No hay peers disponibles para {torrent_hash[:8]}")
                return
            
            logger.info(f"[DOWNLOAD] {len(peers)} peers disponibles: {peers}")
            
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
            
            # 4. Descargar chunks
            downloaded = 0
            for chunk_idx in missing_chunks:
                # Seleccionar peer (simple round-robin)
                peer = peers[chunk_idx % len(peers)]
                peer_ip = peer.get('ip')
                peer_port = peer.get('port')
                
                if not peer_ip or not peer_port:
                    continue
                
                logger.debug(f"[DOWNLOAD] Descargando chunk {chunk_idx} de {peer_ip}:{peer_port}")
                
                # Solicitar chunk
                chunk_data = await self.peer_service.request_chunk(
                    peer_host=peer_ip,
                    peer_port=peer_port,
                    torrent_hash=torrent_hash,
                    chunk_index=chunk_idx,
                    timeout=30.0
                )
                
                if chunk_data:
                    # Escribir chunk al archivo
                    await self._write_chunk(file_path, chunk_idx, chunk_data, torrent_info.chunk_size)
                    downloaded += 1
                    
                    # Actualizar progreso
                    torrent_info.downloaded_chunks = downloaded
                    
                    logger.info(
                        f"[DOWNLOAD] Chunk {chunk_idx} descargado "
                        f"({downloaded}/{len(missing_chunks)}) - "
                        f"{(downloaded/len(missing_chunks)*100):.1f}%"
                    )
                else:
                    logger.warning(f"[DOWNLOAD] Falló descarga de chunk {chunk_idx}")
            
            # 5. Verificar si está completo
            if downloaded == len(missing_chunks):
                torrent_info.is_seeding = True
                torrent_info.downloaded_chunks = torrent_info.total_chunks
                
                # Registrar archivo para seeding
                self.peer_service.register_file(torrent_hash, file_path)
                
                logger.info(f"✅ [DOWNLOAD] Descarga completa: {torrent_info.file_name}")
                
                # Anunciar completado al tracker
                await self.tracker_manager.announce_async(
                    info_hash=torrent_hash,
                    peer_id=self.peer_id,
                    uploaded=0,
                    downloaded=torrent_info.file_size,
                    left=0
                )
            else:
                logger.warning(
                    f"[DOWNLOAD] Descarga incompleta: {downloaded}/{len(missing_chunks)} chunks"
                )
                
        except Exception as e:
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
        logger.info("TorrentClient detenido")
