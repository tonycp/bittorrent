"""
ClientManager - Coordinador principal del cliente BitTorrent.

Responsabilidades:
- Coordinar TrackerManager para comunicación con tracker
- Gestionar torrents registrados
- Proveer API síncrona para la GUI
"""

import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from uuid import uuid4

from ..core.tracker_manager import TrackerManager
from ..core.file_mng import FileManager
from ..config.config_mng import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class TorrentHandle:
    """Representa el estado de un torrent en descarga/compartido"""

    torrent_hash: str
    file_name: str
    file_path: Path
    file_size: int
    chunk_size: int
    total_chunks: int

    # Estado de descarga
    downloaded_chunks: Set[int] = field(default_factory=set)
    pending_chunks: Set[int] = field(default_factory=set)

    # Peers activos
    active_peers: List[Dict[str, Any]] = field(default_factory=list)

    # Estadísticas
    uploaded: int = 0
    downloaded: int = 0

    @property
    def progress(self) -> float:
        """Progreso de descarga (0-100)"""
        if self.total_chunks == 0:
            return 100.0
        return (len(self.downloaded_chunks) / self.total_chunks) * 100.0

    @property
    def is_complete(self) -> bool:
        """Si el torrent está completo"""
        return len(self.downloaded_chunks) == self.total_chunks

    @property
    def remaining(self) -> int:
        """Bytes restantes"""
        downloaded_size = len(self.downloaded_chunks) * self.chunk_size
        return max(0, self.file_size - downloaded_size)


class ClientManager:
    """
    Manager principal que coordina comunicación con tracker.

    Maneja el event loop en un thread separado para mantener la GUI responsiva.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

        # Peer ID único
        self.peer_id = str(uuid4())

        # Servicios core
        self.tracker_manager: Optional[TrackerManager] = None
        self.file_manager: Optional[FileManager] = None

        # Event loop en thread separado
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._running = False

        # Torrents registrados
        self._torrents: Dict[str, TorrentHandle] = {}

    # ==================== Lifecycle ====================

    def start(self):
        """Inicia el cliente (sincrónico, llamado desde GUI)"""
        if self._running:
            logger.warning("ClientManager ya está corriendo")
            return

        self._running = True

        # Crear event loop en thread separado
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

        # Esperar a que el loop arranque
        asyncio.run_coroutine_threadsafe(self._start_services(), self._loop).result()

        logger.info(f"ClientManager iniciado (peer_id={self.peer_id[:8]})")

    def stop(self):
        """Detiene el cliente (sincrónico)"""
        if not self._running:
            return

        self._running = False

        # Detener servicios
        if self._loop:
            future = asyncio.run_coroutine_threadsafe(self._stop_services(), self._loop)
            future.result(timeout=5)

            # Detener loop
            self._loop.call_soon_threadsafe(self._loop.stop)

        # Esperar thread
        if self._loop_thread:
            self._loop_thread.join(timeout=5)

        logger.info("ClientManager detenido")

    def _run_loop(self):
        """Ejecuta el event loop en thread separado"""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _start_services(self):
        """Inicia servicios asíncronos"""
        # Iniciar file manager
        download_path = self.config.get_download_path()
        torrent_path = self.config.get_torrent_path()
        self.file_manager = FileManager(download_path, torrent_path)
        
        # Iniciar tracker manager
        self.tracker_manager = TrackerManager(self.config)
        await self.tracker_manager.start()

        logger.info("FileManager y TrackerManager iniciados")

    async def _stop_services(self):
        """Detiene servicios asíncronos"""
        # Detener tracker manager
        if self.tracker_manager:
            await self.tracker_manager.stop()

        logger.info("Servicios detenidos")

    # ==================== Torrent Management ====================

    def add_torrent(
        self,
        torrent_hash: str,
        file_name: str,
        file_size: int,
        chunk_size: int,
        total_chunks: int,
    ) -> str:
        """
        Añade un torrent para descargar (sincrónico).

        Returns:
            Handle ID del torrent
        """
        if torrent_hash in self._torrents:
            logger.warning(f"Torrent {torrent_hash[:8]} ya existe")
            return torrent_hash

        download_path = Path(self.config.get("General", "download_path"))
        file_path = download_path / file_name

        handle = TorrentHandle(
            torrent_hash=torrent_hash,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            pending_chunks=set(range(total_chunks)),
        )

        self._torrents[torrent_hash] = handle

        # Registrar en tracker
        future = asyncio.run_coroutine_threadsafe(
            self.tracker_manager.register_torrent_async(
                torrent_hash=torrent_hash,
                file_name=file_name,
                file_size=file_size,
                total_chunks=total_chunks,
                piece_length=chunk_size,  # piece_length es el tamaño del chunk
            ),
            self._loop,
        )

        success = future.result(timeout=10)
        if not success:
            logger.error(f"Error registrando torrent {torrent_hash[:8]} en tracker")
        else:
            logger.info(f"Torrent registrado exitosamente: {file_name} ({torrent_hash[:8]})")

        logger.info(f"Torrent agregado: {file_name} ({torrent_hash[:8]})")
        return torrent_hash

    def start_download(self, torrent_hash: str):
        """Inicia la descarga de un torrent (placeholder - descarga real no implementada)"""
        if torrent_hash not in self._torrents:
            logger.error(f"Torrent {torrent_hash[:8]} no encontrado")
            return
        
        # TODO: Implementar descarga real de chunks usando bit_lib
        logger.info(f"Descarga iniciada (placeholder): {torrent_hash[:8]}")

    def pause_download(self, torrent_hash: str):
        """Pausa la descarga de un torrent (placeholder)"""
        # TODO: Implementar pausa de descarga
        logger.info(f"Descarga pausada (placeholder): {torrent_hash[:8]}")

    def remove_torrent(self, torrent_hash: str, delete_files: bool = False):
        """Elimina un torrent"""
        self.pause_download(torrent_hash)

        if torrent_hash in self._torrents:
            handle = self._torrents[torrent_hash]

            # Eliminar archivos si se solicita
            if delete_files and handle.file_path.exists():
                handle.file_path.unlink()
                logger.info(f"Archivo eliminado: {handle.file_path}")

            del self._torrents[torrent_hash]
            logger.info(f"Torrent eliminado: {torrent_hash[:8]}")

    def pause_torrent(self, torrent_hash: str):
        """Alias de pause_download"""
        self.pause_download(torrent_hash)

    def resume_torrent(self, torrent_hash: str):
        """Alias de start_download"""
        self.start_download(torrent_hash)

    # ==================== Download Logic ====================

    async def _download_torrent(self, torrent_hash: str):
        """Lógica principal de descarga de un torrent"""
        try:
            handle = self._torrents[torrent_hash]

            logger.info(
                f"Iniciando descarga de {handle.file_name} ({handle.total_chunks} chunks)"
            )

            # Announce al tracker
            await self.tracker_manager.announce_async(
                info_hash=torrent_hash,
                peer_id=self.peer_id,
                left=handle.remaining,
            )

            # Loop principal de descarga
            while not handle.is_complete and self._running:
                # Obtener peers del tracker
                peers = await self.tracker_manager.get_peers_async(torrent_hash)

                if not peers:
                    logger.warning(f"No hay peers disponibles para {torrent_hash[:8]}")
                    await asyncio.sleep(5)
                    continue

                handle.active_peers = peers
                logger.debug(f"Encontrados {len(peers)} peers para {torrent_hash[:8]}")

                # Descargar chunks pendientes
                await self._download_chunks_from_peers(handle, peers)

                # Announce periódico
                await self.tracker_manager.announce_async(
                    info_hash=torrent_hash,
                    peer_id=self.peer_id,
                    uploaded=handle.uploaded,
                    downloaded=handle.downloaded,
                    left=handle.remaining,
                )

                await asyncio.sleep(1)

            if handle.is_complete:
                logger.info(f"✓ Descarga completa: {handle.file_name}")

        except asyncio.CancelledError:
            logger.info(f"Descarga cancelada: {torrent_hash[:8]}")
        except Exception as e:
            logger.error(f"Error en descarga de {torrent_hash[:8]}: {e}", exc_info=True)

    async def _download_chunks_from_peers(
        self, handle: TorrentHandle, peers: List[Dict[str, Any]]
    ):
        """Descarga chunks pendientes desde peers disponibles"""
        if not handle.pending_chunks:
            return

        # Tomar hasta 5 chunks para descargar en paralelo
        chunks_to_download = list(handle.pending_chunks)[:5]

        tasks = []
        for chunk_idx in chunks_to_download:
            # Seleccionar peer aleatorio
            import random

            peer = random.choice(peers)

            peer_ip = peer.get("ip")
            peer_port = peer.get("port")

            if not peer_ip or not peer_port:
                continue

            task = self._download_chunk(handle, chunk_idx, peer_ip, peer_port)
            tasks.append(task)

        # Ejecutar descargas en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Procesar resultados
        for chunk_idx, result in zip(chunks_to_download, results):
            if isinstance(result, Exception):
                logger.error(f"Error descargando chunk {chunk_idx}: {result}")
            elif result:
                handle.pending_chunks.discard(chunk_idx)
                handle.downloaded_chunks.add(chunk_idx)
                handle.downloaded += handle.chunk_size

    async def _download_chunk(
        self, handle: TorrentHandle, chunk_idx: int, peer_ip: str, peer_port: int
    ) -> bool:
        """Descarga un chunk específico de un peer"""
        try:
            chunk_data = await self.peer_service.request_chunk(
                peer_host=peer_ip,
                peer_port=peer_port,
                torrent_hash=handle.torrent_hash,
                chunk_index=chunk_idx,
                timeout=30.0,
            )

            if chunk_data:
                logger.debug(f"Chunk {chunk_idx} descargado de {peer_ip}:{peer_port}")
                return True

            return False

        except Exception as e:
            logger.error(
                f"Error descargando chunk {chunk_idx} de {peer_ip}:{peer_port}: {e}"
            )
            return False

    # ==================== Query API ====================

    def get_torrent_status(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """Obtiene el estado actual de un torrent"""
        handle = self._torrents.get(torrent_hash)
        if not handle:
            return None

        return {
            "torrent_hash": handle.torrent_hash,
            "file_name": handle.file_name,
            "file_size": handle.file_size,
            "progress": handle.progress,
            "downloaded": handle.downloaded,
            "uploaded": handle.uploaded,
            "peers": len(handle.active_peers),
            "complete": handle.is_complete,
        }

    def get_all_torrents(self) -> List[str]:
        """Obtiene lista de todos los torrents"""
        return list(self._torrents.keys())

    def list_torrents(self) -> Dict[str, TorrentHandle]:
        """Obtiene diccionario de todos los torrents con sus handles"""
        return self._torrents.copy()

    def get_status(self, torrent_hash: str):
        """Alias de get_torrent_status para compatibilidad"""
        from dataclasses import dataclass

        @dataclass
        class TorrentStatus:
            state: str
            total_size: int
            downloaded: int
            download_rate: float
            upload_rate: float
            num_peers: int

        handle = self._torrents.get(torrent_hash)
        if not handle:
            return None

        # Determinar estado
        if handle.is_complete:
            state = "seeding"
        elif handle.pending_chunks:
            state = "downloading"
        else:
            state = "stopped"

        return TorrentStatus(
            state=state,
            total_size=handle.file_size,
            downloaded=len(handle.downloaded_chunks) * handle.chunk_size,
            download_rate=0.0,  # TODO: calcular desde estadísticas
            upload_rate=0.0,  # TODO: calcular desde estadísticas
            num_peers=len(handle.active_peers),
        )
