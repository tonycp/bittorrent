import os, hashlib, json, humanize
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import asdict

from ..connection.network import NetworkManager
from .file_downloader import FileDownloader
from ..interface import TorrentData, DownloadProgress, ChunkInfo
from ..const import TK_URL


class FileManager:
    CHUNK_SIZE = 256 * 1024

    def __init__(self, download_path: str, torrent_path: str):
        self.download_path = download_path
        self.torrent_path = torrent_path
        self.active_downloads: Dict[str, FileDownloader] = {}

        os.makedirs(self.torrent_path, exist_ok=True)
        os.makedirs(self.download_path, exist_ok=True)
        self.load_state()

    # ------------------ Hash utilities ------------------

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(FileManager.CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_chunk_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    # ------------------ State persistence ------------------

    def save_state(self, file: str = "downloads.json") -> None:
        safe_state: Dict[str, Dict[str, Any]] = {}
        path = os.path.join(self.download_path, file)
        for file_hash, downloader in self.active_downloads.items():
            safe_state[file_hash] = downloader.serialize_state()
        with open(path, "w") as f:
            json.dump(safe_state, f, indent=2)

    def load_state(self, file: str = "downloads.json") -> None:
        path = os.path.join(self.download_path, file)
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            data: Dict = json.load(f)
        for file_hash, info in data.items():
            torrent_data = TorrentData(**info["torrent_data"])
            downloader = FileDownloader(info["file_path"], torrent_data)
            downloader.restore_state(info)
            self.active_downloads[file_hash] = downloader

    # ------------------ Torrent operations ------------------

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
                info = ChunkInfo(
                    chunk_id=i,
                    chunk_size=len(chunk_data),
                    display_size=humanize.naturalsize(len(chunk_data), binary=True),
                    chunk_hash=chunk_hash,
                )
                chunks_info.append(info)

        tracker_str = f"{address[0]}:{address[1]}"
        torrent_data = TorrentData(
            file_name=file_name,
            file_size=file_size,
            display_size=humanize.naturalsize(file_size, binary=True),
            file_hash=file_hash,
            chunk_size=self.CHUNK_SIZE,
            total_chunks=total_chunks,
            tracker_address=tracker_str,
            chunks_info=chunks_info,
        )

        # Agregar como torrent activo (ya completo → seeding)
        downloader = FileDownloader(file_path, torrent_data)
        downloader.mark_as_complete()
        self.active_downloads[file_hash] = downloader
        self.save_state()

        # Guardar tormenta
        torrent_file = os.path.join(self.torrent_path, f"{file_name}.p2p")
        with open(torrent_file, "w") as f:
            json.dump(asdict(torrent_data), f, indent=2)

        return torrent_file, torrent_data

    def load_torrent_file(self, torrent_path: str) -> TorrentData:
        if not os.path.exists(torrent_path):
            raise FileNotFoundError(f"Archivo torrent no encontrado: {torrent_path}")
        with open(torrent_path, "r") as f:
            raw: Dict = json.load(f)

        addr = raw.get("tracker_address", raw.get(TK_URL, ""))
        if isinstance(addr, str) and ":" in addr:
            ip, port = addr.split(":")
            raw["tracker_address"] = (ip, int(port))

        return TorrentData(**raw)

    def start_download(
        self,
        torrent_data: TorrentData,
        network_manager: NetworkManager,
    ) -> FileDownloader:
        file_path = os.path.join(self.download_path, torrent_data.file_name)
        file_hash = torrent_data.file_hash

        # Crea el espacio físico si no existe
        if not os.path.exists(file_path):
            with open(file_path, "wb") as f:
                f.seek(torrent_data.file_size - 1)
                f.write(b"\0")

        # Inicializa o recupera Downloader
        downloader = self.active_downloads.get(file_hash)
        if not downloader:
            downloader = FileDownloader(file_path, torrent_data, network_manager)
            self.active_downloads[file_hash] = downloader
        if not downloader.running:
            downloader.start()
        self.save_state()
        return downloader

    def get_all_torrents(self) -> Set[str]:
        return set(self.active_downloads.keys())

    # ------------------ I/O Helpers ------------------

    def get_chunk_for_peer(self, file_hash: str, chunk_id: int) -> Optional[bytes]:
        if file_hash not in self.active_downloads:
            return None
        file_path = self.active_downloads[file_hash].file_path
        try:
            with open(file_path, "rb") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                return f.read(self.CHUNK_SIZE)
        except Exception:
            return None

    def write_chunk(self, file_hash: str, chunk_id: int, chunk_data: bytes) -> bool:
        if file_hash not in self.active_downloads:
            return False
        downloader = self.active_downloads[file_hash]
        try:
            with open(downloader.file_path, "r+b") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                f.write(chunk_data)
            downloader.downloaded_chunks.add(chunk_id)
            downloader.update_progress()
            self.save_state()
            return True
        except Exception:
            return False

    # ------------------ Query Helpers ------------------

    def get_download_progress(self, file_hash: str) -> Optional[DownloadProgress]:
        downloader = self.active_downloads.get(file_hash)
        if not downloader:
            return None
        return DownloadProgress(
            file_name=downloader.file_name,
            file_size=downloader.file_size,
            downloaded_size=downloader.downloaded_size,
            progress=downloader.progress,
            downloaded_chunks=len(downloader.downloaded_chunks),
            total_chunks=downloader.total_chunks,
        )

    def get_missing_chunks(self, file_hash: str) -> List[int]:
        downloader = self.active_downloads.get(file_hash)
        if not downloader:
            return []
        return list(set(range(downloader.total_chunks)) - downloader.downloaded_chunks)

    def remove_download(self, file_hash: str):
        if file_hash in self.active_downloads:
            del self.active_downloads[file_hash]
            self.save_state()
