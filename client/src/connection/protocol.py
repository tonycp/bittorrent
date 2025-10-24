import json, time, uuid
from typing import Dict, Any, Optional, List


class Protocol:
    VERSION = "1.0"

    COMMANDS = {
        "CREATE": "Create",
        "READ": "Get",
        "UPDATE": "Update",
        "DELETE": "Delete",
    }

    @staticmethod
    def create_message(
        controller: str,
        command: str,
        func: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if msg_id is None:
            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        message = {
            "version": Protocol.VERSION,
            "controller": controller,
            "command": command,
            "func": func or "",
            "args": args or {},
            "id": msg_id,
            "timestamp": int(time.time()),
        }
        return message

    @staticmethod
    def encode_message(message: Dict[str, Any]) -> bytes:
        json_str = json.dumps(message)
        json_bytes = json_str.encode("utf-8")
        length = len(json_bytes)
        length_bytes = length.to_bytes(4, byteorder="big")
        return length_bytes + json_bytes

    @staticmethod
    def decode_message(data: bytes) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(data.decode("utf-8"))
        except:
            return None

    @staticmethod
    def create_handshake(
        peer_id: str, client_name: str = "CustomP2P"
    ) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["CREATE"],
            func="handshake",
            args={
                "peer_id": peer_id,
                "client_name": client_name,
                "protocol_version": Protocol.VERSION,
            },
        )

    @staticmethod
    def create_announce(
        info_hash: str,
        peer_id: str,
        ip: str,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        event: Optional[str] = None,
    ) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["CREATE"],
            func="announce",
            args={
                "info_hash": info_hash,
                "peer_id": peer_id,
                "ip": ip,
                "port": port,
                "uploaded": uploaded,
                "downloaded": downloaded,
                "left": left,
                "event": event,
            },
        )

    @staticmethod
    def create_disconnect(peer_id: str, info_hash: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["CREATE"],
            func="disconnect",
            args={
                "peer_id": peer_id,
                "info_hash": info_hash,
            },
        )

    @staticmethod
    def create_keepalive(peer_id: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["UPDATE"],
            func="keepalive",
            args={"peer_id": peer_id},
        )

    @staticmethod
    def create_file_info_request(info_hash: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["READ"],
            func="file_info",
            args={"info_hash": info_hash},
        )

    @staticmethod
    def create_peer_list(info_hash: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["READ"],
            func="peer_list",
            args={"info_hash": info_hash},
        )

    @staticmethod
    def create_scrape(info_hash: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["READ"],
            func="scrape",
            args={"info_hash": info_hash},
        )
