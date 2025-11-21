from pydantic import StrictStr, StrictInt

ANNOUNCE_DATASET = {
    "info_hash": StrictStr,
    "peer_id": StrictStr,
    "ip": StrictStr,
    "port": StrictInt,
    "left": StrictInt,
    "event": StrictStr,
}

HANDSHAKE_DATASET = {
    "peer_id": StrictStr,
    "protocol_version": StrictStr,
}

DISCONNECT_DATASET = {
    "peer_id": StrictStr,
    "info_hash": StrictStr,
}

KEEPALIVE_DATASET = {
    "peer_id": StrictStr,
}

PEER_LIST_DATASET = {
    "info_hash": StrictStr,
}

GET_PEERS_DATASET = {
    "info_hash": StrictStr,
}

FILE_INFO_DATASET = {
    "info_hash": StrictStr,
}

CREATE_TORRENT_DATASET = {
    "info_hash": StrictStr,
    "file_name": StrictStr,
    "file_size": StrictInt,
    "total_chunks": StrictInt,
}
