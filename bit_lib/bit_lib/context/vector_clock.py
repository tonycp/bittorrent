from __future__ import annotations

from typing import Dict
from pydantic import BaseModel, Field


class VectorClock(BaseModel):
    """
    Vector Clock para ordenamiento causal de eventos distribuidos.

    Implementa comparaciones y operaciones de causalidad según Lamport.
    """

    clock: Dict[str, int] = Field(
        default_factory=dict, description="Mapeo tracker_id -> contador"
    )

    def get(self, tracker_id: str) -> int:
        """Obtiene contador para un tracker."""
        return self.clock.get(tracker_id, 0)

    def increment(self, tracker_id: str) -> None:
        """Incrementa contador del tracker."""
        self.clock[tracker_id] = self.get(tracker_id) + 1

    def merge(self, other: VectorClock) -> None:
        """
        Merge: toma máximo de cada componente y luego incrementa local.

        Used cuando se recibe evento remoto.
        """
        all_keys = set(self.clock.keys()) | set(other.clock.keys())
        for k in all_keys:
            self.clock[k] = max(self.get(k), other.get(k))

    def __lt__(self, other: "VectorClock") -> bool:
        """self < other: self happened-before other"""
        all_keys = set(self.clock.keys()) | set(other.clock.keys())
        less_or_equal = all(self.get(k) <= other.get(k) for k in all_keys)
        strictly_less = any(self.get(k) < other.get(k) for k in all_keys)
        return less_or_equal and strictly_less

    def __gt__(self, other: "VectorClock") -> bool:
        """self > other: self happened-after other"""
        all_keys = set(self.clock.keys()) | set(other.clock.keys())
        greater_or_equal = all(self.get(k) >= other.get(k) for k in all_keys)
        strictly_greater = any(self.get(k) > other.get(k) for k in all_keys)
        return greater_or_equal and strictly_greater

    def __le__(self, other: "VectorClock") -> bool:
        """self <= other"""
        return self < other or self == other

    def __ge__(self, other: "VectorClock") -> bool:
        """self >= other"""
        return self > other or self == other

    def __eq__(self, other: object) -> bool:
        """Igualdad: mismos valores en todos los trackers"""
        if not isinstance(other, VectorClock):
            return False
        all_keys = set(self.clock.keys()) | set(other.clock.keys())
        return all(self.get(k) == other.get(k) for k in all_keys)

    def concurrent_with(self, other: "VectorClock") -> bool:
        """Verdadero si events son concurrentes (no comparable)"""
        return not (self < other or self > other or self == other)

    def compare_with(self, other: "VectorClock") -> str:
        """
        Retorna relación causal.

        Returns:
            "before" | "after" | "equal" | "concurrent"
        """
        if self < other:
            return "before"
        elif self > other:
            return "after"
        elif self == other:
            return "equal"
        else:
            return "concurrent"

    def to_dict(self) -> Dict[str, int]:
        """Convierte a Dict para almacenamiento/serialización."""
        return dict(self.clock)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "VectorClock":
        """Crea VectorClock desde Dict."""
        return cls(clock=data)
