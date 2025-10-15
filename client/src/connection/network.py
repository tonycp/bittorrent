import socket
import threading
import time
from .protocol import Protocol

class PeerConnection:
    def __init__(self, host, port, peer_id=None):
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.socket = None
        self.connected = False
        self.last_activity = time.time()
    
    def connect(self):
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
    
    def send_message(self, message):
        try:
            encoded = Protocol.encode_message(message)
            self.socket.sendall(encoded)
            self.last_activity = time.time()
            return True
        except Exception as e:
            print(f"Error enviando mensaje: {e}")
            self.connected = False
            return False
    
    def receive_message(self):
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            
            length = int.from_bytes(length_bytes, byteorder='big')
            
            data = b''
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
    
    def close(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False


class NetworkManager:
    def __init__(self, listen_port, peer_id):
        self.listen_port = listen_port
        self.peer_id = peer_id
        self.peers = {}
        self.server_socket = None
        self.running = False
        self.message_handlers = {}
        self.lock = threading.Lock()
    
    def register_handler(self, command, handler):
        self.message_handlers[command] = handler
    
    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.listen_port))
            self.server_socket.listen(5)
            self.running = True
            
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            
            return True
        except Exception as e:
            print(f"Error iniciando servidor: {e}")
            return False
    
    def _accept_connections(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                peer_conn = PeerConnection(address[0], address[1])
                peer_conn.socket = client_socket
                peer_conn.connected = True
                
                thread = threading.Thread(
                    target=self._handle_peer,
                    args=(peer_conn,),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error aceptando conexión: {e}")
    
    def _handle_peer(self, peer_conn):
        try:
            while peer_conn.connected and self.running:
                message = peer_conn.receive_message()
                
                if message is None:
                    break
                
                command = message.get('command')
                if command in self.message_handlers:
                    self.message_handlers[command](peer_conn, message)
                
        except Exception as e:
            print(f"Error manejando peer: {e}")
        finally:
            peer_conn.close()
    
    def connect_to_peer(self, host, port):
        peer_conn = PeerConnection(host, port)
        if peer_conn.connect():
            handshake = Protocol.create_handshake(self.peer_id)
            if peer_conn.send_message(handshake):
                with self.lock:
                    peer_key = f"{host}:{port}"
                    self.peers[peer_key] = peer_conn
                
                thread = threading.Thread(
                    target=self._handle_peer,
                    args=(peer_conn,),
                    daemon=True
                )
                thread.start()
                
                return True
        return False
    
    def send_to_peer(self, peer_key, message):
        with self.lock:
            if peer_key in self.peers:
                return self.peers[peer_key].send_message(message)
        return False
    
    def broadcast_message(self, message):
        with self.lock:
            for peer in self.peers.values():
                if peer.connected:
                    peer.send_message(message)
    
    def get_connected_peers(self):
        with self.lock:
            return [p for p in self.peers.values() if p.connected]
    
    def stop(self):
        self.running = False
        
        with self.lock:
            for peer in self.peers.values():
                peer.close()
            self.peers.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
