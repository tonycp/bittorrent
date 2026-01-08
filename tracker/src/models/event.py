from __future__ import annotations

from typing import Dict

from bit_lib.models.typing import Data

from .entity import Entity


class EventLog(Entity):
    tracker_id: str
    vector_clock: Dict[str, int]

    # Routing information
    operation: str
    data: Data

    timestamp: int

    def __lt__(self, other: EventLog) -> bool:
        all_keys = set(self.vector_clock.keys()) | set(other.vector_clock.keys())

        less_or_equal = all(self.get(k) <= other.get(k) for k in all_keys)
        strictly_less = any(self.get(k) < other.get(k) for k in all_keys)

        return less_or_equal and strictly_less

    def __gt__(self, other: EventLog) -> bool:
        all_keys = set(self.vector_clock.keys()) | set(other.vector_clock.keys())

        greater_or_equal = all(self.get(k) >= other.get(k) for k in all_keys)
        strictly_greater = any(self.get(k) > other.get(k) for k in all_keys)

        return greater_or_equal and strictly_greater

    def compare_with(self, other: EventLog) -> str:
        if self < other:
            return "before"
        elif self > other:
            return "after"
        else:
            return "concurrent"

    def get(self, tracker_id: str) -> int:
        return self.vector_clock.get(tracker_id, 0)

    def concurrent_with(self, other: EventLog) -> bool:
        return not (self < other or other < self)

    def increment(self, tracker_id: str):
        self.vector_clock[tracker_id] = self.vector_clock.get(tracker_id, 0) + 1
