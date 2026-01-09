from pydantic import StrictStr, StrictInt
from typing import List

from bit_lib.context import VectorClock
from src.models import Peer, Torrent, EventLog


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

# Para replicar lista de eventos incrementales
REPLICATE_EVENTS_DATASET = {
    "source_tracker_id": StrictStr,
    "events": List[EventLog],
}

# Para snapshot inicial (tracker nuevo)
REPLICATE_SNAPSHOT_DATASET = {
    "source_tracker_id": StrictStr,
    "vector_clock": VectorClock,
    "torrents": List[Torrent],
    "peers": List[Peer],
}

# Para solicitar snapshot
REQUEST_SNAPSHOT_DATASET = {
    "tracker_id": StrictStr,
}

# Para heartbeat de trackers
REPLICATION_HEARTBEAT_DATASET = {
    "tracker_id": StrictStr,
    "last_timestamp": StrictInt,
    "event_count": StrictInt,
}
