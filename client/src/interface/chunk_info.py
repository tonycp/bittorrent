from dataclasses import dataclass


@dataclass
class ChunkInfo:
    id: int
    size: int
    hash: str
