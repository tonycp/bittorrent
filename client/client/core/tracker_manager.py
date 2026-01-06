from ..connection.network import NetworkManager
from ..config.utils import get_env_settings
from ..config.config_mng import ConfigManager
from ..connection.peer_conn import PeerConnection


class TrackerManager:
    def __init__(self, config_manager: ConfigManager, network: NetworkManager):
        self.network = network
        self.config_manager = config_manager
        self.env_settings = get_env_settings()

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
            "command": "Get",
            "func": "peer_list",
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
            "command": "Create",
            "func": "announce",
            "args": {
                "info_hash": info_hash,
                "peer_id": peer_id,
                "ip": self.network.client_ip,
                "port": self.config_manager.get_listen_port(),
                "left": 0,
                "event": "started",
            },
            "version": "1.0",
        }
        tracker_host, tracker_port = tracker_address
        PeerConnection.send_request_and_receive_response(
            tracker_host, tracker_port, announce_msg
        )
