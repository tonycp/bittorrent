import os, time, uuid, threading
from typing import Any, Dict, List, Set

from client.src.core.file_downloader import FileDownloader

from ..connection.peer_conn import PeerConnection

from ..config.config_mng import ConfigManager
from ..connection.network import NetworkManager
from ..connection.protocol import Protocol
from .file_mng import FileManager
from ..interface.download import Download


class TorrentClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.peer_id: str = f"P2P-{uuid.uuid4().hex[:12]}"

        self.network_manager: NetworkManager = NetworkManager(
            self.config_manager.get_listen_port(), self.peer_id
        )

        self.file_manager: FileManager = FileManager(
            self.config_manager.get_download_path(),
            self.config_manager.get_torrent_path(),
        )

        self.downloads: Dict[str, Download] = {}
        self.running: bool = False

        self._register_handlers()
        self.setup_session()

    def _register_handlers(self):
        self.network_manager.register_handler("handshake", self._handle_handshake)
        self.network_manager.register_handler(
            "request_chunk", self._handle_chunk_request
        )
        self.network_manager.register_handler("send_chunk", self._handle_chunk_response)
        self.network_manager.register_handler("file_info", self._handle_file_info)

    def _handle_handshake(self, peer_conn: PeerConnection, message: Dict):
        args: Dict[str, Any] = message.get("args", {})
        peer_conn.peer_id = args.get("peer_id")
        print(f"Handshake received from peer: {peer_conn.peer_id}")

        response = Protocol.create_handshake(self.peer_id)
        peer_conn.send_message(response)

    def _handle_chunk_request(self, peer_conn: PeerConnection, message: Dict):
        args: Dict[str, Any] = message.get("args", {})
        file_hash: str = args.get("file_hash")
        chunk_id: int = args.get("chunk_id")

        if file_hash in self.file_manager.files:
            file_path: str = os.path.join(
                self.config_manager.get_download_path(),
                self.file_manager.files[file_hash]["file_name"],
            )

            if os.path.exists(file_path):
                chunk_data: bytes = self.file_manager.get_chunk(file_path, chunk_id)
                if chunk_data:
                    import base64

                    chunk_data_b64: str = base64.b64encode(chunk_data).decode("utf-8")
                    response = Protocol.create_chunk_response(
                        file_hash, chunk_id, chunk_data_b64
                    )
                    peer_conn.send_message(response)

    def _handle_chunk_response(self, peer_conn: PeerConnection, message: Dict):
        args: Dict[str, Any] = message.get("args", {})
        file_hash = args.get("file_hash")
        chunk_id = args.get("chunk_id")
        chunk_data_b64 = args.get("chunk_data")

        if file_hash in self.downloads:
            import base64

            chunk_data: bytes = base64.b64decode(chunk_data_b64)

            if self.file_manager.write_chunk(file_hash, chunk_id, chunk_data):
                download: Download = self.downloads[file_hash]
                download.downloaded_chunks.add(chunk_id)

                progress_info = self.file_manager.get_download_progress(file_hash)
                if progress_info:
                    download.progress = progress_info.progress

                if self.file_manager.is_download_complete(file_hash):
                    download.state = "seeding"
                    print(f"Descarga completed: {download.file_name}")

    def _handle_file_info(self, peer_conn, message):
        pass

    def setup_session(self):
        if not self.running:
            self.network_manager.start_server()
            self.running = True

            update_thread = threading.Thread(target=self._update_loop, daemon=True)
            update_thread.start()

    def _update_loop(self):
        while self.running:
            try:
                self._update_download_stats()
                self._request_missing_chunks()
                time.sleep(1)
            except Exception as e:
                print(f"Error en update loop: {e}")

    def _update_download_stats(self):
        current_time: float = time.time()

        for file_hash, download in self.downloads.items():
            progress_info = self.file_manager.get_download_progress(file_hash)
            if progress_info:
                download.progress = progress_info.progress

                time_diff: float = current_time - download.last_update
                if time_diff > 0:
                    bytes_diff: int = (
                        progress_info.downloaded_size - download.bytes_downloaded_last
                    )
                    download.download_rate = (bytes_diff / time_diff) / 1024

                    download.bytes_downloaded_last = progress_info.downloaded_size
                    download.last_update = current_time

            download.num_peers = len(self.network_manager.get_connected_peers())

    def _request_missing_chunks(self):
        peers = self.network_manager.get_connected_peers()

        if not peers:
            return

        for file_hash, download in self.downloads.items():
            if download.paused or download.state == "seeding":
                continue

            missing_chunks = self.file_manager.get_missing_chunks(file_hash)

            for chunk_id in missing_chunks[:10]:
                for peer in peers[:3]:
                    request = Protocol.create_chunk_request(file_hash, chunk_id)
                    peer.send_message(request)
                    break

    def add_torrent(self, torrent_path: str) -> Download:
        torrent_data = self.file_manager.load_torrent_file(torrent_path)
        file_hash: str = torrent_data.file_hash

        self.file_manager.start_download(torrent_data, self.network_manager)

        download: Download = Download(file_hash, torrent_data)
        self.downloads[file_hash] = download

        return download

    def get_torrent_info(self, torrent_path: str) -> Dict[str, Any]:
        torrent_data = self.file_manager.load_torrent_file(torrent_path)

        return {
            "name": torrent_data.file_name,
            "total_size": torrent_data.file_size,
            "num_files": 1,
            "files": [{"path": torrent_data.file_name, "size": torrent_data.file_size}],
        }

    def get_status(self, download: Download) -> Dict[str, Any]:
        return {
            "file_hash": download.file_hash,
            "name": download.file_name,
            "progress": download.progress,
            "download_rate": download.download_rate,
            "upload_rate": download.upload_rate,
            "num_peers": download.num_peers,
            "num_seeds": 0,
            "state": download.state,
            "total_download": len(download.downloaded_chunks) * FileManager.CHUNK_SIZE,
            "total_upload": 0,
        }

    def get_all_torrents(self) -> Dict[str, Download]:
        return self.downloads

    def exists_torrent(self, file_hash: str) -> bool:
        return file_hash in self.downloads

    def pause_torrent(self, file_hash: str):
        if file_hash not in self.downloads:
            return
        download = self.downloads[file_hash]
        download.state = "paused"
        download.paused = True

    def resume_torrent(self, file_hash: str):
        if file_hash not in self.downloads:
            return
        download = self.downloads[file_hash]
        download.state = "downloading"
        download.paused = False

    def remove_torrent(self, file_hash: str):
        if file_hash not in self.downloads:
            return
        if file_hash in self.downloads:
            del self.downloads[file_hash]
        if file_hash in self.file_manager.active_downloads:
            del self.file_manager.active_downloads[file_hash]

    def connect_to_peer(self, host: str, port: int) -> PeerConnection:
        return self.network_manager.connect_to_peer(host, port)

    def stop(self):
        self.running = False
        self.network_manager.stop()
