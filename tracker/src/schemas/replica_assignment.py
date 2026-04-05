from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from .entity import EntityTable


class ReplicaAssignmentTable(EntityTable):
    __tablename__ = "replica_assignments"

    torrent_hash: Mapped[str] = mapped_column(unique=True, index=True)
    replica_set: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
