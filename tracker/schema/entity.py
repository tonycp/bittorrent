from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime
from datetime import datetime, timezone
from uuid import uuid4

__all__ = ["Entity"]
get_utc = lambda: datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    version: Mapped[int] = mapped_column(Integer, default=0)

    # audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc(),
        onupdate=get_utc(),
        nullable=False,
    )
