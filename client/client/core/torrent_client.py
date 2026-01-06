import uuid
import logging
from typing import Dict, Set, Tuple

from ..connection.peer_conn import PeerConnection
from ..config.config_mng import ConfigManager
from ..connection.network import NetworkManager
from ..connection.protocol import Protocol
from .file_mng import FileManager
from ..interface import TorrentData
from .tracker_manager import TrackerManager


class TorrentClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.peer_id: str = f"P2P-{uuid.uuid4().hex[:12]}"
        self.logger = logging.getLogger(__name__)

        # Configuración base
        self.max_concurrent_chunks = getattr(
            config_manager, "max_concurrent_chunks", 10
        )
        self.max_peers_per_chunk = getattr(config_manager, "max_peers_per_chunk", 3)

        # Componentes principales
        self.network_manager = NetworkManager(
            config_manager.get_listen_port(),
            self.peer_id,
        )
        self.file_manager = FileManager(
            config_manager.get_download_path(),
            config_manager.get_torrent_path(),
        )
        self.tracker_manager = TrackerManager(config_manager, self.network_manager)

        # Descargas activas (directamente instancias de FileDownloader)
        self.active_downloads = self.file_manager.active_downloads
        self.running = False

        # Inicialización de red
        self._register_handlers()
        self._setup_session()

    # -------------------------------------------------
    # Handlers de mensajes P2P
    # -------------------------------------------------
    def _register_handlers(self):
        self.network_manager.register_handler("handshake", self._handle_handshake)
        self.network_manager.register_handler("request_chunk", self._handle_chunk_req)

    def _handle_handshake(self, peer_conn: PeerConnection, message: Dict):
        args: Dict = message.get("args", {})
        peer_id = args.get("peer_id")
        peer_conn.peer_id = peer_id
        self.logger.info(f"Handshake recibido de {peer_id}")
        peer_conn.send_message(Protocol.create_handshake(self.peer_id))

    def _handle_chunk_req(self, peer_conn: PeerConnection, message: Dict):
        print(message)
        args: Dict = message.get("args", {})
        file_hash = args.get("file_hash")
        chunk_id = args.get("chunk_id")
        chunk_data = self.file_manager.get_chunk_for_peer(file_hash, chunk_id)
        if chunk_data:
            response = Protocol.create_chunk_response(chunk_id, chunk_data)
            peer_conn.send_message(response)

    # -------------------------------------------------
    # Ciclo de actualización
    # -------------------------------------------------
    def _setup_session(self):
        if not self.running:
            self.network_manager.start_server()
            self.running = True

    # -------------------------------------------------
    # API de TorrentClient
    # -------------------------------------------------
    def create_torrent_file(
        self, filename: str, tracker_address: Tuple[str, int]
    ) -> Tuple[str, TorrentData]:
        data = self.file_manager.create_torrent_file(filename, tracker_address)
        _, torrent_data = data

        if self.tracker_manager.register_torrent(torrent_data, tracker_address):
            self.logger.info(f"Torrent registrado: {torrent_data.file_name}")
        else:
            self.logger.error("No se pudo registrar el torrent en el tracker.")

        file_hash = torrent_data.file_hash
        self.tracker_manager.announce(file_hash, self.peer_id, tracker_address)
        return data

    def add_torrent(self, torrent_data: TorrentData):
        downloader = self.file_manager.start_download(
            torrent_data, self.network_manager
        )
        self.logger.info(f"Torrent añadido: {downloader.file_name}")
        return downloader

    def get_all_torrents(self) -> Set[str]:
        return self.file_manager.get_all_torrents()

    def get_status(self, file_hash: str):
        return self.file_manager.get_download_progress(file_hash)

    def get_torrent_info(self, file_path: str):
        return self.file_manager.load_torrent_file(file_path)

    def pause_torrent(self, file_hash: str):
        if file_hash in self.active_downloads:
            self.active_downloads[file_hash].pause()

    def resume_torrent(self, file_hash: str):
        if file_hash in self.active_downloads:
            self.active_downloads[file_hash].resume()

    def remove_torrent(self, file_hash: str):
        self.file_manager.remove_download(file_hash)

    def connect_to_peer(self, host: str, port: int) -> PeerConnection:
        return self.network_manager.connect_to_peer(host, port)

    def stop(self):
        self.running = False
        self.network_manager.stop()
        self.logger.info("Cliente torrent detenido.")
