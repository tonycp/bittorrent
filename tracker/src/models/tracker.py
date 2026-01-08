from pydantic import Field

from bit_lib.context import VectorClock
from src.models.entity import Entity


class Tracker(Entity):
    """Modelo Pydantic para tracker en la red distribuida."""
    
    tracker_id: str = Field(..., description="ID único del tracker")
    host: str = Field(..., description="Host del tracker")
    port: int = Field(..., ge=1024, le=65535, description="Puerto del tracker")
    status: str = Field(default="online", description="Estado: online | offline | degraded")
    vector_clock: VectorClock = Field(default_factory=VectorClock, description="Vector clock para causalidad")
