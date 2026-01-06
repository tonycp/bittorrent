from bit_lib import proto

from typing import Optional
from abc import ABC

from .service import MessageService

import asyncio

MProtocol = proto.MessageProtocol
Transport = asyncio.Transport
Event = asyncio.Event


class ClientService(MessageService, ABC):
    def __init__(self):
        self.protocol: Optional[MProtocol] = None
        self.transport: Optional[Transport] = None
        self.connected = Event()

    async def connect(self, host: str, port: int):
        loop = asyncio.get_event_loop()
        factory = self.create_protocol_factory()

        connection = await loop.create_connection(factory, host, port)
        self.transport, self.protocol = connection

        await self.connected.wait()

    async def _on_connect(self, protocol: MProtocol):
        self.connected.set()

    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        self.connected.clear()
