from pydantic import StrictStr, StrictInt
from typing import Dict, Any


# Para crear eventos locales
CREATE_EVENT_DATASET = {
    "tracker_id": StrictStr,
    "operation": StrictStr,  # "peer_announce", "peer_stopped", etc.
    "data": Dict[str, Any],  # payload del evento
}

# Para aplicar eventos remotos
APPLY_EVENT_DATASET = {
    "tracker_id": StrictStr,
    "vector_clock": Dict[str, StrictInt],
    "operation": StrictStr,
    "timestamp": StrictInt,
    "data": Dict[str, Any],
}

# Para queries
GET_LAST_EVENT_DATASET = {
    "tracker_id": StrictStr,
}
