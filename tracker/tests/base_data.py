from uuid import uuid4


class TestData:
    @staticmethod
    def generate_torrent_data():
        return {
            "info_hash": uuid4().hex,
            "file_name": f"test_file_{uuid4().hex[:8]}.torrent",
            "file_size": 1024000,
            "total_chunks": 100,
        }

    @staticmethod
    def generate_peer_data(info_hash=None, event=None, left=None):
        return {
            "info_hash": info_hash or uuid4().hex,
            "peer_id": uuid4().hex,
            "ip": "192.168.1.1",
            "port": 6881,
            "left": left or 1024000,
            "event": event,
        }
