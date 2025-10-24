from dataclasses import dataclass, field
import time
from typing import Set, Dict, Any

from .torrent_data import TorrentData


@dataclass
class Download:
    file_hash: str
    torrent_data: TorrentData
    downloaded_chunks: Set[int] = field(default_factory=set)
    progress: float = 0.0
    download_rate: float = 0.0
    upload_rate: float = 0.0
    num_peers: int = 0
    state: str = "downloading"
    paused: bool = False
    last_update: float = field(default_factory=time.time)
    bytes_downloaded_last: int = 0

    @property
    def file_name(self) -> str:
        return self.torrent_data.file_name

    @property
    def file_size(self) -> int:
        return self.torrent_data.file_size

    @property
    def total_chunks(self) -> int:
        return self.torrent_data.total_chunks

    @classmethod
    def from_torrent_data(cls, torrent_data: TorrentData, file_status: Dict[str, Any]):
        return cls(
            file_hash=torrent_data.file_hash,
            torrent_data=torrent_data,
            downloaded_chunks=file_status.get("downloaded_chunks", set()),
            progress=file_status.get("progress", 0.0),
            state=file_status.get("state", "downloading"),
        )

    def set_state(self, new_state: str):
        self.state = new_state
        self.paused = new_state == "paused"
