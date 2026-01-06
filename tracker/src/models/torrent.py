from pydantic import field_validator, Field
from sqlalchemy.orm.properties import MappedColumn
from typing import Optional
from datetime import datetime

from .entity import Entity


class Peer(Entity):
    ip: str
    port: int

    uploaded: int
    downloaded: int
    left: int

    is_seed: bool
    last_announce: Optional[datetime]
    status: Optional[str]

    protocol_version: Optional[str]

    @field_validator("last_announce", "status", mode="before")
    @classmethod
    def set_audit_default(cls, v):
        return None if isinstance(v, MappedColumn) and v.column.default else v


class Torrent(Entity):
    hash: str = Field(alias="info_hash")
    name: Optional[str]

    size: int
    chunks: int


class TorrentPeer(Entity):
    torrent_id: str
    peer_id: str
