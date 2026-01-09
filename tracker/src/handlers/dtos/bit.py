from pydantic import (
    StrictStr,
    StrictInt,
)

ANNOUNCE_DATASET = {
    "info_hash": StrictStr,
    "peer_id": StrictStr,
    "ip": StrictStr,
    "port": StrictInt,
    "left": StrictInt,
    "event": StrictStr,
}

PEER_LIST_DATASET = {
    "info_hash": StrictStr,
}

GET_PEERS_DATASET = {
    "info_hash": StrictStr,
}
