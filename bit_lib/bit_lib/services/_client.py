from abc import ABC
from typing import Dict, Optional

from bit_lib.errors.errors import BaseError
from bit_lib.proto.protocol import MProtocol
from bit_lib.models import Request, Response, Error

from .base import BitService

import asyncio

Transport = asyncio.Transport
Future = asyncio.Future


class ClientService(BitService, ABC):
    def __init__(self):
        BitService.__init__(self)
        self.loop = asyncio.get_event_loop()
        self._pending_by_proto: Dict[MProtocol, Dict[str, Future]] = {}

    async def _on_connect(self, protocol: MProtocol):
        self._pending_by_proto.setdefault(protocol, {})

    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        pend = self._pending_by_proto.pop(protocol, {})
        for f in pend.values():
            if not f.done():
                f.set_exception(exc)

    async def connect(self, host: str, port: int):
        _, protocol = await self.loop.create_connection(self.factory, host, port)
        return protocol

    async def request(
        self,
        host: str,
        port: int,
        request: Request,
        timeout: float = 5.0,
    ) -> Optional[Response]:
        fut = self.loop.create_future()
        protocol = await self.connect(host, port)
        self._pending_by_proto[protocol][request.msg_id] = fut

        protocol.send_message(request)
        return await asyncio.wait_for(fut, timeout=timeout)

    def get_future(self, proto: MProtocol, resp: Response) -> Optional[Future]:
        if resp.reply_to:
            pend = self._pending_by_proto.get(proto, {})
            fut = pend.pop(resp.reply_to, None)
            if fut and not fut.done():
                return fut

    async def _handle_response(self, protocol: MProtocol, response: Response):
        fut = self.get_future(protocol, response)
        if fut:
            fut.set_result(response)

    async def _handle_error(self, protocol: MProtocol, error: Error):
        fut = self.get_future(protocol, error)
        if fut:
            err = BaseError(**error.data)
            fut.set_exception(err)
