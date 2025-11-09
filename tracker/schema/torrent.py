from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    Boolean,
    BigInteger,
    ForeignKey,
    Table,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from datetime import datetime

from .entity import Entity, get_utc

__all__ = ["Torrent", "Peer", "torrent_peers"]


torrent_peers = Table(
    "torrent_peers",
    Entity.metadata,
    Column("torrent_id", String(36), ForeignKey("torrents.id"), primary_key=True),
    Column("peer_id", String(36), ForeignKey("peers.id"), primary_key=True),
)


class Torrent(Entity):
    __tablename__ = "torrents"
    info_hash: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Añadir estos campos sugeridos:
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Puedes agregar más como chunk_size, fecha de creación, comentario...

    peers: Mapped[List["Peer"]] = relationship(
        "Peer",
        secondary=torrent_peers,
        back_populates="torrents",
        lazy="dynamic",  # Opcional para eficiencia con muchos peers
    )


class Peer(Entity):
    __tablename__ = "peers"

    # Datos de red
    peer_id: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        nullable=False,
    )
    ip: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)

    # Estado de avance
    # uploaded: Mapped[int] = mapped_column(BigInteger, default=0)
    # downloaded: Mapped[int] = mapped_column(BigInteger, default=0)
    left: Mapped[int] = mapped_column(BigInteger, default=0)

    # Estado y auditoría
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_announce: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc(),
        nullable=False,
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
    )  # Para extensibilidad ('leech', 'seed', 'stopped', etc.)

    # Datos del cliente
    client_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    protocol_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    torrents: Mapped[List["Torrent"]] = relationship(
        "Torrent",
        secondary=torrent_peers,
        back_populates="peers",
        lazy="dynamic",  # Opcional para eficiencia
    )


# Índices extra (opcional)
Index("ix_torrents_info_hash", Torrent.info_hash)
Index("ix_peers_peer_id", Peer.peer_id)
Index("ix_peers_is_seed", Peer.is_seed)
Index("ix_peers_last_announce", Peer.last_announce)
