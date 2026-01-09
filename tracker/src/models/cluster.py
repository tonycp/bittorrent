from __future__ import annotations

from pydantic import BaseModel, Field
from bit_lib.context import CacheManager, VectorClock

from .tracker import Tracker


class TrackerState(BaseModel):
    """Estado de un tracker en el cluster para coordinación."""

    tracker_id: str
    host: str
    port: int
    vector_clock: VectorClock = Field(default_factory=VectorClock)
    is_coordinator: bool = False
    query_count: int = 0


class ClusterState(TrackerState):
    """Estado del cluster local con cache de otros trackers"""

    coordinator_id: str | None = None
    cache: CacheManager[TrackerState] | None = None

    class Config:
        arbitrary_types_allowed = True


class CausalityViolation(BaseModel):
    """Representa una violación de causalidad detectada."""

    tracker_id: str
    event_id: str
    expected_clock: VectorClock = Field(default_factory=VectorClock)
    actual_clock: VectorClock = Field(default_factory=VectorClock)
