from __future__ import annotations
from advanced_alchemy.base import orm_registry
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, ForeignKey, Table, Index

from typing import List, Optional
from datetime import datetime

from .entity import EntityTable


torrent_peers = Table(
    "torrent_peers",
    orm_registry.metadata,
    Column(
        "torrent_id",
        ForeignKey("torrents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "peer_id",
        ForeignKey("peers.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TorrentTable(EntityTable):
    __tablename__ = "torrents"
    info_hash: Mapped[str] = mapped_column(unique=True)
    name: Mapped[Optional[str]]

    size: Mapped[int]
    chunks: Mapped[int]

    peers: Mapped[List[PeerTable]] = relationship(
        secondary=torrent_peers,
        back_populates="torrents",
        lazy="selectin",
    )


class PeerTable(EntityTable):
    __tablename__ = "peers"
    ip: Mapped[str]
    port: Mapped[int]

    # Estado de avance
    uploaded: Mapped[int] = mapped_column(default=0)
    downloaded: Mapped[int] = mapped_column(default=0)
    left: Mapped[int] = mapped_column(default=0)

    # Estado y auditoría
    is_seed: Mapped[bool] = mapped_column(default=False)
    last_announce: Mapped[Optional[datetime]]
    status: Mapped[Optional[str]]

    # Datos del cliente
    protocol_version: Mapped[Optional[str]]

    torrents: Mapped[List[TorrentTable]] = relationship(
        secondary=torrent_peers,
        back_populates="peers",
        lazy="selectin",
    )


# Índices extra (opcional)
Index("ix_peers_is_seed", PeerTable.is_seed)
Index("ix_torrents_info_hash", TorrentTable.info_hash)
Index("ix_peers_last_announce", PeerTable.last_announce)
