from bit_lib.models.message import MetaData
from bit_lib.proto.protocol import MProtocol

from typing import Optional
from abc import ABC, abstractmethod
from bit_lib.models import (
    MessageUnion,
)


class MessageService(ABC):
    def create_protocol_factory(self):
        def protocol_factory():
            return MProtocol(
                self._handle_message,
                self._handle_binary,
                self._on_connect,
                self._on_disconnect,
            )

        return protocol_factory

    @abstractmethod
    async def _handle_message(self, protocol: MProtocol, message: MessageUnion):
        pass

    @abstractmethod
    async def _handle_binary(self, protocol: MProtocol, meta: MetaData, data: bytes):
        pass

    @abstractmethod
    async def _on_connect(self, protocol: MProtocol):
        pass

    @abstractmethod
    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        pass

    async def send_message(self, protocol: MProtocol, message: MessageUnion):
        if protocol and message:
            protocol.send_message(message)

    async def send_binary(self, protocol: MProtocol, metadata: MetaData, data: bytes):
        if protocol:
            protocol.send_binary(metadata, data)
