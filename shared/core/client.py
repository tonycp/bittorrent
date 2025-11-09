from typing import Optional
from shared.core.service import MessageService
from shared.proto import MessageProtocol as MProtocol


import asyncio
from abc import ABC


class ClientService(MessageService, ABC):
    def __init__(self):
        self.protocol: Optional[MProtocol] = None
        self.transport: Optional[asyncio.Transport] = None
        self.connected = asyncio.Event()

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
