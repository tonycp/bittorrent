from pydantic import (
    StrictStr,
)


HANDSHAKE_DATASET = {
    "peer_id": StrictStr,
    "info_hash": StrictStr,
    "protocol_version": StrictStr,
}

DISCONNECT_DATASET = {
    "peer_id": StrictStr,
    "info_hash": StrictStr,
}

KEEPALIVE_DATASET = {
    "peer_id": StrictStr,
}
