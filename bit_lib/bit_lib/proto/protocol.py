from bit_lib.const import c_proto as cp

from typing import (
    Callable,
    Optional,
    TypeAlias,
)
from bit_lib.models import (
    BaseMessage,
    MessageUnion,
)
from bit_lib.models.message import MetaData

from .message import DSerial

import asyncio

MProtocol: TypeAlias = "MessageProtocol"
DataCallback: TypeAlias = Callable[[MProtocol, MetaData, bytes], None]
MSGCallback: TypeAlias = Callable[[MProtocol, MessageUnion], None]
DCallback: TypeAlias = Callable[[MProtocol, Exception], None]
CCallback: TypeAlias = Callable[[MProtocol], None]

Protocol = asyncio.Protocol
Transport = asyncio.Transport


class MessageProtocol(Protocol):
    transport: Optional[Transport]

    def __init__(
        self,
        message_callbac: MSGCallback,
        data_chunk_callback: DataCallback,
        connection_callback: Optional[CCallback] = None,
        disconnect_callback: Optional[DCallback] = None,
    ):
        self.transport = None
        self.message_callbac = message_callbac
        self.data_chunk_callback = data_chunk_callback
        self.connection_callback = connection_callback
        self.disconnect_callback = disconnect_callback
        self.buffer = b""

    def connection_made(self, transport: Transport):
        self.transport = transport
        self._on_connect()

    def data_received(self, data: bytes):
        self.buffer += data
        self._process_data()

    def connection_lost(self, exc: Optional[Exception]):
        self.transport = None
        self._on_disconnect(exc)

    def send_message(self, message: BaseMessage):
        msg_type = cp.MSG_TYPE_JSON.to_bytes(1, cp.BYTEORDER)
        data = DSerial.encode_message(message)
        data = msg_type + DSerial.add_head(data)
        if self.transport:
            self.transport.write(data)

    def send_binary(self, metadata: MetaData, data_bin: bytes):
        msg_type = cp.MSG_TYPE_BINARY.to_bytes(1, cp.BYTEORDER)
        data = DSerial.encode_data(metadata, data_bin)
        data = msg_type + DSerial.add_head(data)
        if self.transport:
            self.transport.write(data)

    def _get_size(self) -> int:
        size_bytes = self.buffer[1 : cp.SIZE_MSG]
        return int.from_bytes(size_bytes, cp.BYTEORDER)

    def _process_data(self):
        while len(self.buffer) >= cp.SIZE_MSG:
            size = self._get_size()
            if len(self.buffer) < cp.SIZE_MSG + size:
                break

            msg_type = self.buffer[0]
            end_index = cp.SIZE_MSG + size

            message = self.buffer[cp.SIZE_MSG : end_index]
            self._handle_message(msg_type, message)

            self.buffer = self.buffer[end_index:]

    def _handle_message(self, msg_type: int, msg_bytes: bytes):
        if msg_type == cp.MSG_TYPE_JSON:
            callback = self.message_callbac
            msg = DSerial.decode_message(msg_bytes)
            return self._execute_callback(callback, msg)

        if msg_type == cp.MSG_TYPE_BINARY:
            callback = self.data_chunk_callback
            metadata, data = DSerial.decode_data(msg_bytes)
            return self._execute_callback(callback, metadata, data)

        raise ValueError("Unknown message type")

    def _on_connect(self):
        callback = self.connection_callback
        self._execute_callback(callback)

    def _on_disconnect(self, exc: Optional[Exception]):
        callback = self.disconnect_callback
        self._execute_callback(callback, exc)

    def _execute_callback(self, callback, *args, **kwargs):
        if not callback:
            return
        asyncio.create_task(self._run_callback(callback, *args, **kwargs))

    async def _run_callback(self, callback, *args, **kwargs):
        result = callback(self, *args, **kwargs)
        if asyncio.iscoroutine(result):
            await result
