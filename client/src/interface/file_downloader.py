from dataclasses import dataclass, field
from typing import Set

from .torrent_data import TorrentData


@dataclass
class FileDownloader:
    file_path: str
    file_name: str
    file_size: int
    total_chunks: int
    torrent_data: TorrentData
    downloaded_chunks: Set[int] = field(default_factory=set)
    downloaded_size: int = 0
