from bit_lib import proto

from abc import ABC, abstractmethod
from bit_lib.models import (
    Data,
    MessageUnion,
    decode_request,
    process_header,
)
from bit_lib.models.message import Request, Response

from .service import MessageService

import asyncio

MProtocol = proto.MessageProtocol


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
    async def _handle_message(self, protocol: MProtocol, message: MessageUnion):
        if isinstance(message, Request):
            await self._handle_request(protocol, message)

    async def _handle_request(self, protocol: MProtocol, request: Request):
        header, data = decode_request(request)

        route, hdl_key = process_header(header)

        response = await self._dispatch_message(route, hdl_key, data, request.msg_id)

        await self.send_message(protocol, response)

    @abstractmethod
    async def _dispatch_message(
        self,
        route: str,
        hdl_key: str,
        data: Data,
        msg_id: str = None,
    ) -> Response:
        pass
