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
    def create_file_info_request(file_hash: str) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["GET"],
            func="file_info",
            args={"file_hash": file_hash},
        )

    @staticmethod
    def create_file_info_response(
        file_hash: str, file_name: str, file_size: int, total_chunks: int
    ) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["GET"],
            func="file_info",
            args={
                "file_hash": file_hash,
                "file_name": file_name,
                "file_size": file_size,
                "total_chunks": total_chunks,
            },
        )

    @staticmethod
    def create_chunk_request(file_hash: str, chunk_id: int) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["GET"],
            func="request_chunk",
            args={"file_hash": file_hash, "chunk_id": chunk_id},
        )

    @staticmethod
    def create_chunk_response(
        file_hash: str, chunk_id: int, chunk_data: bytes
    ) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["GET"],
            func="send_chunk",
            args={
                "file_hash": file_hash,
                "chunk_id": chunk_id,
                "chunk_data": chunk_data,
            },
        )

    @staticmethod
    def create_announce(peer_id: str, files_available: List[str]) -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",
            Protocol.COMMANDS["CREATE"],
            func="announce",
            args={"peer_id": peer_id, "files": files_available},
        )

    @staticmethod
    def create_keepalive() -> Dict[str, Any]:
        return Protocol.create_message(
            "TrackerController",Protocol.COMMANDS["UPDATE"], func="keepalive")
