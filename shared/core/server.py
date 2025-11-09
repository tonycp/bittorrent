from abc import ABC
from shared.interface.header import decode_request
from shared.interface.header import process_header

from .dispatcher import Dispatcher
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


class HandlerService(HostService):
    def __init__(self, host, port, dispatcher: Dispatcher):
        super().__init__(host, port)

        self.dispatcher = dispatcher

    async def _handle_message(self, protocol, request):
        header, data = decode_request(request)

        route, hdl_key = process_header(header)
        response = self.dispatcher.dispatch(route, hdl_key, data)

        await self.send_message(protocol, response)
