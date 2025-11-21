from typing import Optional
from abc import ABC, abstractmethod
from shared.proto import MessageProtocol as MProtocol, DataSerialize as dts
from shared.models import Request, MetaData
from shared.const import c_proto as cp


class MessageService(ABC):
    def create_protocol_factory(self):
        def protocol_factory():
            return MProtocol(
                self._on_response,
                self._on_connect,
                self._on_disconnect,
            )

        return protocol_factory

    @abstractmethod
    async def _handle_message(self, protocol: MProtocol, request: Request):
        pass

    @abstractmethod
    async def _handle_binary(self, protocol: MProtocol, meta: MetaData, data: bytes):
        pass

    async def _on_response(self, protocol: MProtocol, msg_type: int, message: bytes):
        if msg_type == cp.MSG_TYPE_JSON:
            request = dts.decode_message(message)
            await self._handle_message(protocol, request)
        else:
            meta, data = dts.decode_data(message)
            await self._handle_binary(protocol, meta, data)

    @abstractmethod
    async def _on_connect(self, protocol: MProtocol):
        pass

    @abstractmethod
    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        pass

    async def send_message(self, protocol: MProtocol, message: Request):
        if protocol and message:
            protocol.send_message(message)

    async def send_binary(self, protocol: MProtocol, metadata: MetaData, data: bytes):
        if protocol:
            protocol.send_binary(metadata, data)
