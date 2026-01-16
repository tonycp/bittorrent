from abc import ABC
from typing import Dict, Optional

from bit_lib.errors.errors import BaseError
from bit_lib.proto.protocol import MProtocol
from bit_lib.models import Request, Response, Error

from .base import BitService

import asyncio
import logging

Transport = asyncio.Transport
Future = asyncio.Future

logger = logging.getLogger(__name__)


class ClientService(BitService, ABC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.loop = asyncio.get_event_loop()
        self._pending_by_proto: Dict[MProtocol, Dict[str, Future]] = {}

    async def _on_connect(self, protocol: MProtocol):
        self._pending_by_proto.setdefault(protocol, {})

    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        pend = self._pending_by_proto.pop(protocol, {})
        for f in pend.values():
            if not f.done():
                f.set_exception(exc or ConnectionError("Disconnected"))

    async def connect(self, host: str, port: int):
        _, protocol = await self.loop.create_connection(self.factory, host, port)
        return protocol

    async def request(
        self,
        host: str,
        port: int,
        request: Request,
        timeout: float = 5.0,
    ) -> Response:
        fut: Future[Response] = self.loop.create_future()
        # Debug logging
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"ClientService.request: about to connect to {host}:{port}")
        protocol = await self.connect(host, port)
        self._pending_by_proto.setdefault(protocol, {})[request.msg_id] = fut

        protocol.send_message(request)
        a = await asyncio.wait_for(fut, timeout=timeout)
        return a

    def get_future(self, proto: MProtocol, resp: Response) -> Optional[Future]:
        if resp.reply_to:
            pend = self._pending_by_proto.get(proto, {})
            fut = pend.pop(resp.reply_to, None)
            logger.debug(
                f"ClientService: resolving future for reply_to={resp.reply_to}"
                + f", found={fut is not None}"
            )
            if fut and not fut.done():
                return fut

    async def _handle_response(self, protocol: MProtocol, response: Response):
        fut = self.get_future(protocol, response)
        if fut:
            logger.debug(
                f"ClientService: setting result for future reply_to={response.reply_to}"
                + f", response={response}"
            )
            fut.set_result(response)

    async def _handle_error(self, protocol: MProtocol, error: Error):
        fut = self.get_future(protocol, error)
        if fut:
            err = BaseError(**error.data)
            logger.debug(
                f"ClientService: setting exception for future reply_to={error.reply_to}"
                + f", error={err}"
            )
            fut.set_exception(err)
