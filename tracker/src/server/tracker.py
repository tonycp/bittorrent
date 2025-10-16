from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from typing import Any, Dict
from ..repos.middleware import DBM
from socket import SocketType
from ..core import handle_request, extract_header
from ..connection import Protocol  # importa el módulo común de protocolo
import logging


class TrackerHandler(BaseRequestHandler):
    request: SocketType
    middleware: DBM

    def handle(self) -> None:
        try:
            length_bytes = self.request.recv(4)
            if not length_bytes or len(length_bytes) < 4:
                return
            length = int.from_bytes(length_bytes, byteorder="big")

            data = b""
            while len(data) < length:
                chunk = self.request.recv(length - len(data))
                if not chunk:
                    return
                data += chunk

            session_exec = self.middleware(self.process_request)
            session_exec(data=data)
        finally:
            self.request.close()

    def process_request(self, handlers: Dict[str, Any], data: bytes) -> None:
        try:

            request_dict = Protocol.decode_message(data)
            header, data_prs = extract_header(request_dict)
            response_obj: str = handle_request(header, data_prs, handlers)
            # Codificar respuesta usando el framing del protocolo
            response_bytes = Protocol.encode_message(response_obj)
            self.request.sendall(response_bytes)
        except Exception as e:
            logging.error(f"Petición inválida: {e}")
            error_bytes = Protocol.encode_message({"error": str(e)})
            self.request.sendall(error_bytes)


class ThreadedServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True

    def __init__(self, address, handler_class, middleware):
        super().__init__(address, handler_class)
        handler_class.middleware = middleware
