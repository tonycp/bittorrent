from abc import ABC, abstractmethod
from typing import Optional

from bit_lib.proto.protocol import MProtocol, MessageProtocol
from bit_lib.models import (
    MessageUnion,
    Error,
    MetaData,
    Request,
    Response,
)


class MessageService(ABC):
    def __init__(self):
        self.factory = self._create_protocol_factory()

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

    def _create_protocol_factory(self):
        def protocol_factory():
            return MessageProtocol(
                self._handle_message,
                self._handle_binary,
                self._on_connect,
                self._on_disconnect,
            )

        return protocol_factory


# TODO: register messages as tasks for tracking and cancellation
class BitService(MessageService, ABC):
    @abstractmethod
    async def _handle_request(self, protocol: MProtocol, request: Request):
        pass

    @abstractmethod
    async def _handle_response(self, protocol: MProtocol, response: Response):
        pass

    @abstractmethod
    async def _handle_error(self, protocol: MProtocol, error: Error):
        pass

    async def process_message(self, protocol, message):
        if isinstance(message, Request):
            await self._handle_request(protocol, message)
        elif isinstance(message, Error):
            await self._handle_error(protocol, message)
        elif isinstance(message, Response):
            await self._handle_response(protocol, message)
        else:
            raise NotImplementedError("Unsupported message type")

    async def send_message(self, protocol: MProtocol, message: MessageUnion):
        if protocol and message:
            protocol.send_message(message)

    async def send_binary(self, protocol: MProtocol, metadata: MetaData, data: bytes):
        if protocol:
            protocol.send_binary(metadata, data)

    async def _handle_message(self, protocol: MProtocol, message: MessageUnion):
        await self.process_message(protocol, message)
