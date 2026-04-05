from abc import ABC
from typing import Optional

from .base import BitService

import asyncio


class HostService(BitService, ABC):
    def __init__(self, host: str, port: int, loop: Optional[asyncio.AbstractEventLoop] = None, **kwargs):
        super().__init__(**kwargs)

        self.host = host
        self.port = port
        # Usar el loop proporcionado si está disponible, sino obtener el actual
        self.loop = loop or asyncio.get_event_loop()
        self.server: Optional[asyncio.base_events.Server] = None

    async def run(self):
        args = self.factory, self.host, self.port
        self.server = await self.loop.create_server(*args)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    