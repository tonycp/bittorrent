from sqlalchemy import Column, String, Integer, JSON, Index

from src.schemas.entity import EntityTable


class TrackerTable(EntityTable):
    """SQLAlchemy ORM model para tracker."""
    
    __tablename__ = "trackers"
    
    tracker_id = Column(String(255), nullable=False, unique=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="online")  # online | offline | degraded
    vector_clock = Column(JSON, nullable=False, default=dict)
    
    # Índice para queries de trackers activos por status
    __table_args__ = (
        Index("ix_status", "status"),
    )
    
    def __repr__(self):
        return f"<Tracker {self.tracker_id}@{self.host}:{self.port} [{self.status}]>"
