from bit_lib.context import VectorClock
from pydantic import StrictStr, StrictInt
from typing import Any


# Para crear eventos locales
CREATE_EVENT_DATASET = {
    "tracker_id": StrictStr,
    "operation": StrictStr,  # "peer_announce", "peer_stopped", etc.
    "data": Any,  # payload del evento - usar Any simple
}

# Para aplicar eventos remotos
APPLY_EVENT_DATASET = {
    "tracker_id": StrictStr,
    "vector_clock": VectorClock,  # Dict[tracker_id] = timestamp
    "operation": StrictStr,
    "timestamp": StrictInt,
    "data": Any,  # payload del evento
}

# Para queries
GET_LAST_EVENT_DATASET = {
    "tracker_id": StrictStr,
}
