ANNOUNCE_DATASET = {
    "info_hash": str,
    "peer_id": str,
    "ip": str,
    "port": int,
    "uploaded": int,
    "downloaded": int,
    "left": int,
    "event": str,  # opcional, puede ser 'started', 'stopped', 'completed'
}

GET_PEERS_DATASET = {
    "info_hash": str,
}
