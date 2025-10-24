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

HANDSHAKE_DATASET = {
    "peer_id": str,
    "client_name": str,
    "protocol_version": str,
}

DISCONNECT_DATASET = {
    "peer_id": str,
    "info_hash": str,
}

KEEPALIVE_DATASET = {
    "peer_id": str,
}

PEER_LIST_DATASET = {
    "info_hash": str,
}

GET_PEERS_DATASET = {
    "info_hash": str,
}

FILE_INFO_DATASET = {
    "info_hash": str,
}

CREATE_TORRENT_DATASET = {
    "info_hash": str,
    "file_name": str,
    "file_size": int,
    "total_chunks": int,
}
