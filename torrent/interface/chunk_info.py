from dataclasses import dataclass


@dataclass
class ChunkInfo:
    chunk_id: int
    chunk_size: int
    display_size: str
    chunk_hash: str
