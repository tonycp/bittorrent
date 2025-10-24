from ..connection.peer_conn import PeerConnection


class TrackerManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def register_torrent(self, torrent_data, tracker_address):
        create_msg = {
            "controller": "TrackerController",
            "command": "Create",
            "func": "create_torrent",
            "args": {
                "info_hash": torrent_data.file_hash,
                "file_name": torrent_data.file_name,
                "file_size": torrent_data.file_size,
                "total_chunks": torrent_data.total_chunks,
            },
            "version": "1.0",
        }

        tracker_host, tracker_port = tracker_address

        response = PeerConnection.send_request_and_receive_response(
            tracker_host, tracker_port, create_msg
        )

        return response is not None and response.get("status") == "ok"

    def get_peers(self, info_hash, tracker_address):
        get_msg = {
            "controller": "TrackerController",
            "command": "GetPeers",
            "func": "get_peers",
            "args": {"info_hash": info_hash},
            "version": "1.0",
        }

        tracker_host, tracker_port = tracker_address

        response = PeerConnection.send_request_and_receive_response(
            tracker_host, tracker_port, get_msg
        )

        if response and response.get("status") == "ok":
            # List of dicts with 'host' and 'port'
            return response.get("peers", [])
        return []

    def announce(self, info_hash, peer_id, tracker_address):
        announce_msg = {
            "controller": "TrackerController",
            "command": "Announce",
            "func": "announce",
            "args": {"info_hash": info_hash, "peer_id": peer_id},
            "version": "1.0",
        }
        tracker_host, tracker_port = tracker_address
        PeerConnection.send_request_and_receive_response(
            tracker_host, tracker_port, announce_msg
        )
