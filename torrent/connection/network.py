import socket
import threading
from typing import Optional, Dict, Any, Callable, List

from .peer_conn import PeerConnection
from .protocol import Protocol


class NetworkManager:
    def __init__(self, listen_port: int, peer_id: str):
        hostname = socket.gethostname()
        self.client_ip = socket.gethostbyname(hostname)
        self.listen_port = listen_port
        self.peer_id = peer_id
        self.peers: Dict[str, PeerConnection] = {}
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.message_handlers: Dict[
            str, Callable[[PeerConnection, Dict[str, Any]], None]
        ] = {}
        self.lock = threading.Lock()
        self.tracker_conn: Optional[PeerConnection] = None

    def register_handler(
        self, func: str, handler: Callable[[PeerConnection, Dict[str, Any]], None]
    ) -> None:
        self.message_handlers[func] = handler

    def start_server(self) -> bool:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.client_ip, self.listen_port))
            self.server_socket.listen(5)
            self.running = True

            accept_thread = threading.Thread(
                target=self._accept_connections, daemon=True
            )
            accept_thread.start()
            print(self.server_socket)

            return True
        except Exception as e:
            print(f"Error iniciando servidor: {e}")
            return False

    def _accept_connections(self) -> None:
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                peer_conn = PeerConnection(address[0], address[1])
                peer_conn.socket = client_socket
                peer_conn.connected = True
                print(peer_conn)

                thread = threading.Thread(
                    target=self._handle_peer, args=(peer_conn,), daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error aceptando conexión: {e}")

    def _handle_peer(self, peer_conn: PeerConnection) -> None:
        try:
            while peer_conn.connected and self.running:
                message = peer_conn.receive_message()
                print(message)
                if message is None:
                    break
                command = message.get("command")
                if command in self.message_handlers:
                    self.message_handlers[command](peer_conn, message)
        except Exception as e:
            print(f"Error manejando peer: {e}")
        finally:
            peer_conn.close()

    def connect_to_peer(self, host: str, port: int) -> bool:
        peer_conn = PeerConnection(host, port)
        if peer_conn.connect():
            handshake = Protocol.create_handshake(self.peer_id)
            if peer_conn.send_message(handshake):
                with self.lock:
                    peer_key = f"{host}:{port}"
                    self.peers[peer_key] = peer_conn

                thread = threading.Thread(
                    target=self._handle_peer, args=(peer_conn,), daemon=True
                )
                thread.start()

                return True
        return False

    def send_to_peer(self, peer_key: str, message: Dict[str, Any]) -> bool:
        with self.lock:
            if peer_key in self.peers:
                return self.peers[peer_key].send_message(message)
        return False

    def broadcast_message(self, message: Dict[str, Any]) -> None:
        with self.lock:
            for peer in self.peers.values():
                if peer.connected:
                    peer.send_message(message)

    def get_connected_peers(self) -> List[PeerConnection]:
        with self.lock:
            return [p for p in self.peers.values() if p.connected]

    # --- Métodos para comunicación con el tracker ---

    def connect_to_tracker(self, tracker_host: str, tracker_port: int) -> bool:
        self.tracker_conn = PeerConnection(tracker_host, tracker_port)
        return self.tracker_conn.connect()

    def send_to_tracker(self, message: Dict[str, Any]) -> bool:
        if self.tracker_conn and self.tracker_conn.connected:
            return self.tracker_conn.send_message(message)
        return False

    def receive_from_tracker(self) -> Optional[Dict[str, Any]]:
        print(self.tracker_conn)
        print(self.tracker_conn.connected)
        if self.tracker_conn and self.tracker_conn.connected:
            return self.tracker_conn.receive_message()
        return None

    def stop(self) -> None:
        self.running = False

        with self.lock:
            for peer in self.peers.values():
                peer.close()
            self.peers.clear()

        if self.tracker_conn:
            self.tracker_conn.close()
            self.tracker_conn = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
