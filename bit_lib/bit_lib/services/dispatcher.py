from abc import ABC, abstractmethod

from bit_lib.context import Dispatcher
from bit_lib.models import (
    Data,
    Request,
    decode_request,
    process_header,
)
from ._host import HostService

from .base import MProtocol


__all__ = ["DispatcherService", "UniqueService"]


class DispatcherService(HostService, ABC):
    def __init__(
        self,
        host: str,
        port: int,
        dispatcher: Dispatcher,
    ):
        HostService.__init__(self, host, port)
        self.dispatcher = dispatcher

    async def _dispatch_request(self, route: str, key: str, *args, **kwargs):
        return await self.dispatcher.dispatch(route, key, *args, **kwargs)

    async def _handle_request(self, protocol: MProtocol, request: Request):
        header, data = decode_request(request)
        route, hdl_key = process_header(header)

        args = data, request.msg_id
        response = await self._dispatch_request(route, hdl_key, *args)
        return await self.send_message(protocol, response)


class UniqueService(HostService, ABC):
    def __init__(
        self,
        host: str,
        port: int,
        service_id: str,
    ):
        super().__init__(host, port)
        self.service_id = service_id

    async def _handle_request(self, protocol: MProtocol, request: Request):
        if response := await self._process_request(request):
            return await self.send_message(protocol, response)

    async def _process_request(self, request: Request):
        header, data = decode_request(request)
        route, hdl_key = process_header(header)

        if route != self.service_id:
            return await self._dispatch_request(hdl_key, data, request.msg_id)

    @abstractmethod
    async def _dispatch_request(self, hdl_key: str, data: Data, msg_id: str):
        pass
