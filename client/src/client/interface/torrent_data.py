from dataclasses import dataclass, field
from typing import List, Tuple

from .chunk_info import ChunkInfo


@dataclass
class TorrentData:
    file_name: str
    file_size: int
    display_size: str
    file_hash: str
    chunk_size: int
    total_chunks: int
    tracker_address: Tuple[str, int]
    chunks_info: List[ChunkInfo] = field(default_factory=list)
