from dataclasses import dataclass, field
import time
from typing import Set

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
