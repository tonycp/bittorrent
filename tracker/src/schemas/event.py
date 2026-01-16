from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .entity import EntityTable


class EventTable(EntityTable):
    __tablename__ = "events"

    tracker_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vector_clock: Mapped[dict] = mapped_column(JSON, nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    replicated_to: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
