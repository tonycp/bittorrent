from dataclasses import dataclass
from typing import List, Optional

__all__ = ["PeerDTO", "TorrentDTO"]


@dataclass
class PeerDTO:
    peer_id: str
    ip: str
    port: int
    uploaded: int
    downloaded: int
    left: int
    last_announce: int
    is_seed: bool


@dataclass
class TorrentDTO:
    info_hash: str
    name: Optional[str]
    peers: List[PeerDTO]
