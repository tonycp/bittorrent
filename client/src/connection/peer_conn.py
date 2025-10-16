import socket, time
from typing import Any, Dict, Optional

from .protocol import Protocol


class PeerConnection:
    def __init__(self, host: str, port: int, peer_id: Optional[str] = None):
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.last_activity = time.time()

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.connected = True
            return True
        except Exception as e:
            print(f"Error conectando a {self.host}:{self.port} - {e}")
            self.connected = False
            return False

    def send_message(self, message: Dict[str, Any]) -> bool:
        try:
            encoded = Protocol.encode_message(message)
            self.socket.sendall(encoded)
            self.last_activity = time.time()
            return True
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
            self.connected = False
            return False

    def receive_message(self) -> Optional[Dict[str, Any]]:
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None

            length = int.from_bytes(length_bytes, byteorder="big")

            data = b""
            while len(data) < length:
                chunk = self.socket.recv(min(length - len(data), 4096))
                if not chunk:
                    return None
                data += chunk

            self.last_activity = time.time()
            return Protocol.decode_message(data)
        except socket.timeout:
            return None
        except Exception as e:
            print(f"Error recibiendo mensaje: {e}")
            self.connected = False
            return None

    def close(self) -> None:
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
