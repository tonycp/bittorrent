import os
import json
import socket
import threading
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import asdict


from ..connection.peer_conn import PeerConnection
from ..config.utils import get_env_settings
from ..const.env import CLT_HOST, CLT_PORT
from ..interface.chunk_info import ChunkInfo
from ..interface.torrent_data import TorrentData
from ..connection.network import NetworkManager
from ..connection.protocol import Protocol


class FileDownloader(threading.Thread):
    def __init__(
        self,
        file_path: str,
        torrent_data: TorrentData,
        network_manager: Optional[NetworkManager] = None,
    ):
        super().__init__(daemon=True)
        self.file_path = file_path
        self.torrent_data = torrent_data
        self.network_manager = network_manager
        self.downloaded_chunks = set()
        self.downloaded_size = 0
        self.progress = 0.0
        self.running = False
        self.state = "paused"
        self.peers: list[Dict[str, Any]] = []
        self.last_update = time.time()
        self.download_rate = 0.0
        self.num_peers = 0

        # Información del entorno
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        settings = get_env_settings({CLT_HOST: ip})
        self.peer_id = network_manager.peer_id if network_manager else f"LOCAL-{ip}"
        self.client_ip = settings[CLT_HOST]
        self.client_port = settings.get(CLT_PORT, 0)

        # Registra receptor de chunks (si hay red)
        if self.network_manager:
            self.network_manager.register_handler(
                "send_chunk", self.handle_chunk_response
            )

    # -------------------------------------------------------
    # Propiedades
    # -------------------------------------------------------
    @property
    def file_name(self) -> str:
        return self.torrent_data.file_name

    @property
    def file_size(self) -> int:
        return self.torrent_data.file_size

    @property
    def total_chunks(self) -> int:
        return self.torrent_data.total_chunks

    @property
    def tracker_address(self) -> Tuple[str, int]:
        return self.torrent_data.tracker_address

    # -------------------------------------------------------
    # Tracker y peers
    # -------------------------------------------------------
    def tracker_request(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        host, port = self.tracker_address
        return PeerConnection.send_request_and_receive_response(host, port, msg)

    def connect_to_tracker(self):
        handshake = Protocol.create_handshake(self.peer_id)
        self.tracker_request(handshake)

        announce = Protocol.create_announce(
            info_hash=self.torrent_data.file_hash,
            peer_id=self.peer_id,
            ip=self.client_ip,
            port=self.client_port,
            uploaded=0,
            downloaded=self.downloaded_size,
            left=self.file_size - self.downloaded_size,
            event="started",
        )
        self.tracker_request(announce)

        peer_list = Protocol.create_peer_list(info_hash=self.torrent_data.file_hash)
        peer_resp = self.tracker_request(peer_list)
        self.peers = peer_resp.get("peers", []) if peer_resp else []

    # -------------------------------------------------------
    # Descarga/loop
    # -------------------------------------------------------
    def select_peer_for_chunk(self, chunk_index: int) -> Optional[Dict[str, Any]]:
        return self.peers[chunk_index % len(self.peers)] if self.peers else None

    def download_loop(self):
        self.running = True
        self.state = "downloading"
        for i in range(self.total_chunks):
            if not self.running:
                break
            if i in self.downloaded_chunks:
                continue

            peer = self.select_peer_for_chunk(i)
            if not peer:
                time.sleep(0.5)
                continue
            
            peer_key = f"{peer['ip']}:{peer['port']}"
            self.network_manager.connect_to_peer(peer['ip'], peer['port'])
            message = Protocol.create_chunk_request(self.torrent_data.file_hash, i)
            print(peer_key, message)
            self.network_manager.send_to_peer(peer_key, message)

            start = time.time()
            while i not in self.downloaded_chunks and self.running:
                if time.time() - start > 5:
                    break
                time.sleep(0.1)
            self.update_progress()

    def handle_chunk_response(self, message: Dict[str, Any]):
        args: Dict = message.get("args", {})
        chunk_id = args.get("chunk_id")
        chunk_data = args.get("chunk_data")
        if chunk_id is None or chunk_data is None:
            return
        if chunk_id in self.downloaded_chunks:
            return

        try:
            print(message)
            with open(self.file_path, "r+b") as f:
                offset = chunk_id * self.torrent_data.chunk_size
                f.seek(offset)
                f.write(chunk_data)
            self.downloaded_chunks.add(chunk_id)
            self.downloaded_size += len(chunk_data)
            self.update_progress()
            self.save_state()
        except Exception as e:
            print(f"[ERROR] al escribir chunk {chunk_id}: {e}")

    # -------------------------------------------------------
    # Estado & progreso
    # -------------------------------------------------------
    def update_progress(self):
        if self.total_chunks > 0:
            self.progress = (len(self.downloaded_chunks) / self.total_chunks) * 100
        if self.progress >= 100:
            self.transition_to_seeding()

    def mark_as_complete(self):
        self.downloaded_chunks = set(range(self.total_chunks))
        self.downloaded_size = sum(map(_get_size, self.torrent_data.chunks_info))
        self.update_progress()
        self.save_state()

    def transition_to_seeding(self):
        self.state = "seeding"
        self.running = False
        self.remove_state()

    # -------------------------------------------------------
    # Ciclo de ejecución hilo
    # -------------------------------------------------------
    def run(self):
        self.connect_to_tracker()
        self.download_loop()

    # -------------------------------------------------------
    # Control manual
    # -------------------------------------------------------
    def pause(self):
        self.state = "paused"
        self.running = False
        self.save_state()

    def resume(self):
        if not self.running:
            self.running = True
            self.state = "downloading"
            threading.Thread(target=self.download_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.save_state()

    # -------------------------------------------------------
    # Serialización / persistencia
    # -------------------------------------------------------
    def serialize_state(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "torrent_data": asdict(self.torrent_data),
            "downloaded_chunks": list(self.downloaded_chunks),
            "state": self.state,
            "progress": self.progress,
            "downloaded_size": self.downloaded_size,
        }

    def restore_state(self, info: Dict[str, Any]):
        self.downloaded_chunks = set(info.get("downloaded_chunks", []))
        self.progress = info.get("progress", 0.0)
        self.downloaded_size = info.get("downloaded_size", 0)
        self.state = info.get("state", "paused")

    def save_state(self):
        """Guarda un archivo .part con los chunks descargados."""
        temp_file = f"{self.file_path}.part"
        data = {
            "chunks": list(self.downloaded_chunks),
            "progress": self.progress,
            "state": self.state,
        }
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self):
        temp_file = f"{self.file_path}.part"
        if not os.path.exists(temp_file):
            return
        with open(temp_file, "r") as f:
            data = json.load(f)
        self.downloaded_chunks = set(data.get("chunks", []))
        self.state = data.get("state", "paused")
        self.progress = data.get("progress", 0.0)

    def remove_state(self):
        temp_file = f"{self.file_path}.part"
        if os.path.exists(temp_file):
            os.remove(temp_file)


def _get_size(x: ChunkInfo):
    return x.chunk_size
