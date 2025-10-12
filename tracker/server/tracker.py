from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from typing import Any, Dict, List, Type

from ..repos.middleware import DBM
from socket import SocketType

from ..core import handle_request, extract_header

import json, logging


class TrackerHandler(BaseRequestHandler):
    request: SocketType
    middleware: DBM

    def handle(self) -> None:
        try:
            data = self.request.recv(4096)
            if data:
                session_exec = self.middleware(self.process_request)
                session_exec(data=data)
        finally:
            self.request.close()

    def process_request(self, handlers: Dict[str, Any], data: bytes) -> None:
        try:
            request = json.loads(data.decode())
            header, data_prs = extract_header(request)
            response: str = handle_request(header, data_prs, handlers)
            self.request.sendall(response.encode())
        except Exception as e:
            logging.error(f"Petición inválida: {e}")
            error_response: str = json.dumps({"error": str(e)})
            self.request.sendall(error_response.encode())


class ThreadedServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True

    def __init__(self, address, handler_class, middleware):
        super().__init__(address, handler_class)
        handler_class.middleware = middleware
