from __future__ import annotations

from bit_lib.models.typing import Data
from bit_lib.context import VectorClock

from .entity import Entity


class EventLog(Entity):
    tracker_id: str
    vector_clock: VectorClock

    # Routing information
    operation: str
    data: Data

    timestamp: int

    def __lt__(self, other: EventLog) -> bool:
        return self.vector_clock < other.vector_clock

    def __gt__(self, other: EventLog) -> bool:
        return self.vector_clock > other.vector_clock

    def compare_with(self, other: EventLog) -> str:
        return self.vector_clock.compare_with(other.vector_clock)

    def concurrent_with(self, other: EventLog) -> bool:
        return self.vector_clock.concurrent_with(other.vector_clock)

    def increment(self, tracker_id: str):
        self.vector_clock.increment(tracker_id)
