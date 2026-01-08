from pydantic import StrictStr, StrictInt


PEER_ANNOUNCE_DATASET = {
    "ip": StrictStr,
    "port": StrictInt,
    "peer_id": StrictStr,
    "torrent_hash": StrictStr,
    "uploaded": StrictInt,
    "downloaded": StrictInt,
    "left": StrictInt,
}

PEER_STOPPED_DATASET = {
    "torrent_hash": StrictStr,
    "peer_id": StrictStr,
}

PEER_COMPLETED_DATASET = {
    "peer_id": StrictStr,
}