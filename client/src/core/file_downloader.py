import threading, time
from typing import Tuple, Dict, Any
from ..interface.torrent_data import TorrentData
from ..connection.network import NetworkManager
from ..connection.protocol import Protocol


class FileDownloader(threading.Thread):
    def __init__(
        self,
        file_path: str,
        torrent_data: TorrentData,
        network_manager: NetworkManager,
    ):
        super().__init__()
        self.file_path = file_path
        self.file_name = torrent_data.file_name
        self.file_size = torrent_data.file_size
        self.total_chunks = torrent_data.total_chunks
        self.tracker_address = torrent_data.tracker_address
        self.torrent_data = torrent_data
        self.downloaded_chunks = set()
        self.downloaded_size = 0
        self.progress = 0.0
        self.running = True
        self.peers = []
        self.network_manager = network_manager
        # Registro del handler para datos entrantes
        self.network_manager.register_handler("send_chunk", self.handle_chunk_response)

    def connect_to_tracker(self):
        # Aquí pondrías la lógica real para obtener los peers desde el tracker;
        # para demo, peers estático:
        self.peers = [
            {"ip": "192.168.0.2", "port": 6881},
            {"ip": "192.168.0.3", "port": 6882},
        ]

    def download_loop(self):
        for chunk_index in range(self.total_chunks):
            if not self.running:
                break
            if chunk_index in self.downloaded_chunks:
                continue
            peer = self.select_peer_for_chunk(chunk_index)
            if peer:
                peer_key = f"{peer['ip']}:{peer['port']}"
                message = Protocol.create_chunk_request(
                    self.torrent_data.file_hash, chunk_index
                )
                self.network_manager.send_to_peer(peer_key, message)
                # Esperar a que el handler procese la respuesta
                wait_time = 0
                while (
                    chunk_index not in self.downloaded_chunks
                    and wait_time < 5
                    and self.running
                ):
                    time.sleep(0.1)
                    wait_time += 0.1
                self.update_progress()
            else:
                time.sleep(0.5)

    def select_peer_for_chunk(self, chunk_index):
        if not self.peers:
            return None
        # Aquí podría ir lógica de priorización, rarest-first, etc.
        return self.peers[chunk_index % len(self.peers)]

    def handle_chunk_response(self, peer_conn, message: Dict[str, Any]):
        args = message.get("args", {})
        chunk_id = args.get("chunk_id")
        chunk_data = args.get("chunk_data")
        if chunk_id is not None and chunk_data is not None:
            with open(self.file_path, "rb+") as f:
                offset = chunk_id * self.torrent_data.chunk_size
                f.seek(offset)
                f.write(chunk_data)
            self.downloaded_chunks.add(chunk_id)
            self.downloaded_size += len(chunk_data)
            print(f"Chunk {chunk_id} recibido y guardado")

    def update_progress(self):
        self.progress = (len(self.downloaded_chunks) / self.total_chunks) * 100
        print(f"Progreso: {self.progress:.2f}%")

    def run(self):
        self.connect_to_tracker()
        self.download_loop()
        print("Descarga finalizada")

    def stop(self):
        self.running = False
