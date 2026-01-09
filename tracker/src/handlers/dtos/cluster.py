"""Datasets para handlers de cluster."""

from pydantic import StrictStr, StrictInt
from bit_lib.context import VectorClock

from src.models.cluster import TrackerState


# Dataset para JOIN: tracker remoto anuncia su presencia con su estado completo
JOIN_DATASET = {
    "remote": TrackerState,  # TrackerState directamente
}

# Dataset para HEARTBEAT: liveness check periódico
CLUSTER_HEARTBEAT_DATASET = {
    "tracker_id": StrictStr,
    "query_count": StrictInt,
    "vector_clock": VectorClock,
}

# Dataset para VIEW: solicitar vista del cluster (sin parámetros, solo GET)
VIEW_DATASET = {}

# Dataset para NORMALIZE: líder envía delta de normalización
NORMALIZE_DATASET = {
    "delta": StrictInt,
}

# Dataset para ELECTION: votación de coordinador (opcional, para coordinación explícita)
ELECTION_DATASET = {
    "candidate_id": StrictStr,
    "query_count": StrictInt,
}
