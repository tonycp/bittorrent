from dataclasses import asdict
import os
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from ..connection.network import NetworkManager
from .file_downloader import FileDownloader
from ..interface import TorrentData, DownloadProgress, ChunkInfo
from ..const import TK_URL


class FileManager:
    CHUNK_SIZE = 256 * 1024

    def __init__(
        self,
        download_path: str,
        torrent_path: str,
    ):
        self.download_path = download_path
        self.torrent_path = torrent_path
        self.files: Dict[str, TorrentData] = {}
        self.active_downloads: Dict[str, FileDownloader] = {}
        self.load_state()

        os.makedirs(torrent_path, exist_ok=True)
        os.makedirs(self.download_path, exist_ok=True)

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(FileManager.CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_chunk_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def save_state(self, file: str = "downloads.json") -> None:
        safe_state: Dict[str, List[str]] = {}
        for key, value in self.active_downloads.items():
            value = dict(value)
            value["downloaded_chunks"] = list(value["downloaded_chunks"])
            safe_state[key] = value

        with open(file, "w") as f:
            json.dump(safe_state, f)

    def load_state(self, file: str = "downloads.json") -> None:
        if not os.path.exists(file):
            return

        with open(file, "r") as f:
            raw: Dict[str, List[str]] = json.load(f)

        for key, value in raw.items():
            file_downloader = FileDownloader(**value)
            self.active_downloads[key] = file_downloader

    def create_torrent_file(
        self, file_path: str, address: Tuple[str, int]
    ) -> Tuple[str, TorrentData]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        file_size = os.path.getsize(file_path)
        file_hash = self.calculate_file_hash(file_path)
        file_name = os.path.basename(file_path)

        total_chunks = (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE

        chunks_info = []
        with open(file_path, "rb") as f:
            for i in range(total_chunks):
                chunk_data = f.read(self.CHUNK_SIZE)
                chunk_hash = self.calculate_chunk_hash(chunk_data)
                info = ChunkInfo(i, len(chunk_data), chunk_hash)
                chunks_info.append(info)

        address_str = f"{address[0]}:{address[1]}"
        torrent_data = TorrentData(
            file_name,
            file_size,
            file_hash,
            self.CHUNK_SIZE,
            total_chunks,
            address_str,
            chunks_info,
        )

        path = os.path.join(self.torrent_path, os.path.basename(file_path))
        torrent_file = f"{path}.p2p"
        with open(torrent_file, "w") as f:
            json.dump(asdict(torrent_data), f, indent=2)

        return torrent_file, torrent_data

    def load_torrent_file(self, torrent_path: str) -> TorrentData:
        if not os.path.exists(torrent_path):
            raise FileNotFoundError(f"Archivo torrent no encontrado: {torrent_path}")

        with open(torrent_path, "r") as f:
            raw: Dict[str, Any] = json.load(f)

        # Adaptar tracker_address si es necesario
        address_raw = raw.get(TK_URL, "")
        if isinstance(address_raw, str) and ":" in address_raw:
            ip, port = address_raw.split(":")
            raw[TK_URL] = (ip, int(port))

        try:
            torrent_data = TorrentData(**raw)
        except TypeError as e:
            raise ValueError(f"El archivo torrent no es válido: {e}")

        self.files[torrent_data.file_hash] = torrent_data
        return torrent_data

    def get_chunk(self, file_path: str, chunk_id: int) -> Optional[bytes]:
        try:
            with open(file_path, "rb") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                chunk_data = f.read(self.CHUNK_SIZE)
                return chunk_data
        except Exception as e:
            print(f"Error leyendo chunk {chunk_id}: {e}")
            return None

    def write_chunk(self, file_hash: str, chunk_id: int, chunk_data: bytes) -> bool:
        if file_hash not in self.active_downloads:
            return False

        download = self.active_downloads[file_hash]
        file_path = download.file_path

        try:
            with open(file_path, "r+b") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                f.write(chunk_data)

            download.downloaded_chunks.add(chunk_id)
            download.downloaded_size += len(chunk_data)

            return True
        except Exception as e:
            print(f"Error escribiendo chunk {chunk_id}: {e}")
            return False

    def start_download(
        self, torrent_data: TorrentData, network_manager: NetworkManager
    ) -> str:
        file_hash = torrent_data.file_hash
        file_name = torrent_data.file_name
        file_size = torrent_data.file_size

        file_path = os.path.join(self.download_path, file_name)

        with open(file_path, "wb") as f:
            f.seek(file_size - 1)
            f.write(b"\0")

        self.active_downloads[file_hash] = FileDownloader(
            file_path, torrent_data, network_manager
        )

        return file_hash

    def get_download_progress(self, file_hash: str) -> Optional[DownloadProgress]:
        if file_hash not in self.active_downloads:
            return None

        download = self.active_downloads[file_hash]
        progress = len(download.downloaded_chunks) / download.total_chunks * 100

        return DownloadProgress(
            download.file_name,
            download.file_size,
            download.downloaded_size,
            progress,
            len(download.downloaded_chunks),
            download.total_chunks,
        )

    def get_missing_chunks(self, file_hash: str) -> List[int]:
        if file_hash not in self.active_downloads:
            return []

        download = self.active_downloads[file_hash]
        all_chunks = set(range(download.total_chunks))
        missing = all_chunks - download.downloaded_chunks

        return list(missing)

    def is_download_complete(self, file_hash: str) -> bool:
        if file_hash not in self.active_downloads:
            return False

        download = self.active_downloads[file_hash]
        return len(download.downloaded_chunks) == download.total_chunks
