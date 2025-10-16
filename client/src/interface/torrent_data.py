from dataclasses import dataclass, field
from typing import List, Tuple

from .chunk_info import ChunkInfo


@dataclass
class TorrentData:
    file_name: str
    file_size: int
    file_hash: str
    chunk_size: int
    total_chunks: int
    tracker_addres: Tuple[str, int]
    chunks: List[ChunkInfo] = field(default_factory=list)
