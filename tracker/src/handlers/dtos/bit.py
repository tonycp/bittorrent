from pydantic import (
    StrictStr,
    StrictInt,
)
from typing import Optional

ANNOUNCE_DATASET = {
    "info_hash": StrictStr,
    "peer_id": StrictStr,
    "ip": StrictStr,
    "port": StrictInt,
    "left": StrictInt,
    "event": Optional[StrictStr],
}

PEER_LIST_DATASET = {
    "info_hash": StrictStr,
}

GET_PEERS_DATASET = {
    "info_hash": StrictStr,
}
