from typing import Callable, Optional, Dict, Any, TypeAlias
from asyncio import Protocol, Transport
import asyncio

from shared.const import c_proto as cp
from .message import DataSerialize as dts

MProtocol: TypeAlias = "MessageProtocol"
RCallback: TypeAlias = Callable[[MProtocol, int, bytes], None]
CCallback: TypeAlias = Callable[[MProtocol], None]
DCallback: TypeAlias = Callable[[MProtocol, Exception], None]


class MessageProtocol(Protocol):
    transport: Optional[asyncio.Transport]

    def __init__(
        self,
        response_callback: RCallback,
        connection_callback: Optional[CCallback] = None,
        disconnect_callback: Optional[DCallback] = None,
    ):
        self.transport = None
        self.response_callback = response_callback
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

    def send_message(self, message: Dict[str, Any]):
        msg_type = cp.MSG_TYPE_JSON.to_bytes(1, cp.BYTEORDER)
        data = dts.encode_message(message)
        data = msg_type + dts.add_size(data)
        if self.transport:
            self.transport.write(data)

    def send_binary(self, metadata: dict, binary_data: bytes):
        msg_type = cp.MSG_TYPE_BINARY.to_bytes(1, cp.BYTEORDER)
        data = dts.encode_data(metadata, binary_data)
        data = msg_type + dts.add_size(data)
        if self.transport:
            self.transport.write(data)

    def _process_data(self):
        while len(self.buffer) >= cp.SIZE_MSG:
            msg_type, message = self._extract_message()
            if not message:
                break
            self._handle_message(msg_type, message)

    def _extract_message(self) -> Optional[bytes]:
        msg_type = self.buffer[0]
        size_bytes = self.buffer[1 : cp.SIZE_MSG]
        size = int.from_bytes(size_bytes, cp.BYTEORDER)

        if len(self.buffer) < cp.SIZE_MSG + size:
            return None

        message = self.buffer[cp.SIZE_MSG : cp.SIZE_MSG + size]
        self.buffer = self.buffer[cp.SIZE_MSG + size :]
        return msg_type, message

    def _handle_message(self, msg_type: int, message: bytes):
        callback = self.response_callback
        self._execute_callback(callback, msg_type, message)

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
