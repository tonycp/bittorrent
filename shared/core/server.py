from abc import ABC, abstractmethod
from shared.models.header import decode_request, process_header
from shared.proto import MessageProtocol as MProtocol
from shared.models.typing import Data
from shared.models import Request

from .service import MessageService

import asyncio


class HostService(MessageService, ABC):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    async def run(self):
        loop = asyncio.get_event_loop()
        factory = self.create_protocol_factory()

        server = await loop.create_server(factory, self.host, self.port)

        async with server:
            await server.serve_forever()


class HandlerService(HostService, ABC):
    async def _handle_message(self, protocol: MProtocol, request: Request):
        header, data = decode_request(request)

        route, hdl_key = process_header(header)
        response = await self._dispatch_message(route, hdl_key, data)

        await self.send_message(protocol, response)

    @abstractmethod
    async def _dispatch_message(self, route: str, hdl_key: str, data: Data) -> Data:
        pass
