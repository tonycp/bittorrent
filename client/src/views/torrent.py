import os
import time
import uuid
import threading
from ..connection.network import NetworkManager
from ..connection.protocol import Protocol
from .file import FileManager


class Download:
    def __init__(self, file_hash, torrent_data):
        self.file_hash = file_hash
        self.torrent_data = torrent_data
        self.file_name = torrent_data["file_name"]
        self.file_size = torrent_data["file_size"]
        self.total_chunks = torrent_data["total_chunks"]
        self.downloaded_chunks = set()
        self.progress = 0.0
        self.download_rate = 0.0
        self.upload_rate = 0.0
        self.num_peers = 0
        self.state = "downloading"
        self.paused = False
        self.last_update = time.time()
        self.bytes_downloaded_last = 0


class TorrentClient:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.peer_id = f"P2P-{uuid.uuid4().hex[:12]}"

        self.network_manager = NetworkManager(
            self.config_manager.get_listen_port(), self.peer_id
        )

        self.file_manager = FileManager(self.config_manager.get_download_path())

        self.downloads = {}
        self.running = False

        self._register_handlers()
        self.setup_session()

    def _register_handlers(self):
        self.network_manager.register_handler(
            Protocol.COMMANDS["HANDSHAKE"], self._handle_handshake
        )
        self.network_manager.register_handler(
            Protocol.COMMANDS["REQUEST_CHUNK"], self._handle_chunk_request
        )
        self.network_manager.register_handler(
            Protocol.COMMANDS["SEND_CHUNK"], self._handle_chunk_response
        )
        self.network_manager.register_handler(
            Protocol.COMMANDS["FILE_INFO"], self._handle_file_info
        )

    def _handle_handshake(self, peer_conn, message):
        args = message.get("args", {})
        peer_conn.peer_id = args.get("peer_id")
        print(f"Handshake recibido de peer: {peer_conn.peer_id}")

        response = Protocol.create_handshake(self.peer_id)
        peer_conn.send_message(response)

    def _handle_chunk_request(self, peer_conn, message):
        args = message.get("args", {})
        file_hash = args.get("file_hash")
        chunk_id = args.get("chunk_id")

        if file_hash in self.file_manager.files:
            file_path = os.path.join(
                self.config_manager.get_download_path(),
                self.file_manager.files[file_hash]["file_name"],
            )

            if os.path.exists(file_path):
                chunk_data = self.file_manager.get_chunk(file_path, chunk_id)
                if chunk_data:
                    import base64

                    chunk_b64 = base64.b64encode(chunk_data).decode("utf-8")
                    response = Protocol.create_chunk_response(
                        file_hash, chunk_id, chunk_b64
                    )
                    peer_conn.send_message(response)

    def _handle_chunk_response(self, peer_conn, message):
        args = message.get("args", {})
        file_hash = args.get("file_hash")
        chunk_id = args.get("chunk_id")
        chunk_data_b64 = args.get("chunk_data")

        if file_hash in self.downloads:
            import base64

            chunk_data = base64.b64decode(chunk_data_b64)

            if self.file_manager.write_chunk(file_hash, chunk_id, chunk_data):
                download = self.downloads[file_hash]
                download.downloaded_chunks.add(chunk_id)

                progress_info = self.file_manager.get_download_progress(file_hash)
                if progress_info:
                    download.progress = progress_info["progress"]

                if self.file_manager.is_download_complete(file_hash):
                    download.state = "seeding"
                    print(f"Descarga completada: {download.file_name}")

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
        current_time = time.time()

        for file_hash, download in self.downloads.items():
            progress_info = self.file_manager.get_download_progress(file_hash)
            if progress_info:
                download.progress = progress_info["progress"]

                time_diff = current_time - download.last_update
                if time_diff > 0:
                    bytes_diff = (
                        progress_info["downloaded_size"]
                        - download.bytes_downloaded_last
                    )
                    download.download_rate = (bytes_diff / time_diff) / 1024

                    download.bytes_downloaded_last = progress_info["downloaded_size"]
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

    def add_torrent(self, torrent_path):
        torrent_data = self.file_manager.load_torrent_file(torrent_path)
        file_hash = torrent_data["file_hash"]

        self.file_manager.start_download(torrent_data)

        download = Download(file_hash, torrent_data)
        self.downloads[file_hash] = download

        return download

    def get_torrent_info(self, torrent_path):
        torrent_data = self.file_manager.load_torrent_file(torrent_path)

        return {
            "name": torrent_data["file_name"],
            "total_size": torrent_data["file_size"],
            "num_files": 1,
            "files": [
                {"path": torrent_data["file_name"], "size": torrent_data["file_size"]}
            ],
        }

    def get_status(self, download):
        return {
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

    def get_all_torrents(self):
        return list(self.downloads.values())

    def pause_torrent(self, download):
        if isinstance(download, Download):
            download.paused = True
            download.state = "paused"

    def resume_torrent(self, download):
        if isinstance(download, Download):
            download.paused = False
            download.state = "downloading"

    def remove_torrent(self, download):
        if isinstance(download, Download):
            file_hash = download.file_hash
            if file_hash in self.downloads:
                del self.downloads[file_hash]
            if file_hash in self.file_manager.active_downloads:
                del self.file_manager.active_downloads[file_hash]

    def connect_to_peer(self, host, port):
        return self.network_manager.connect_to_peer(host, port)

    def stop(self):
        self.running = False
        self.network_manager.stop()
