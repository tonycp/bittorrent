from dataclasses import dataclass
from typing import Optional


@dataclass
class BlockInfo:
    offset: int
    size: int
    data: Optional[bytes] = None
    received: bool = False
