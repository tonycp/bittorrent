from bit_lib.const import c_proto as cp

from typing import (
    Tuple,
    TypeAlias,
)
from bit_lib.models import (
    BaseMessage,
    MessageUnion,
)
from bit_lib.models.message import MetaData
from pydantic import TypeAdapter

# Runtime alias to the concrete serializer class
DSerial = None  # will be set after class definition

# TypeAdapter for MessageUnion to enable validation of discriminated union
_message_adapter = TypeAdapter(MessageUnion)


class DataSerialize:
    VERSION = cp.PROTOCOL_VERSION

    @staticmethod
    def add_head(data: bytes) -> bytes:
        head = len(data).to_bytes(cp.SIZE_HEAD, cp.BYTEORDER)
        return head + data

    @staticmethod
    def split_head(msg: bytes) -> Tuple[int, bytes]:
        if len(msg) < cp.SIZE_HEAD:
            return 0, msg
        head = msg[: cp.SIZE_HEAD]
        data = msg[cp.SIZE_HEAD :]
        size = int.from_bytes(head, cp.BYTEORDER)
        return size, data

    @staticmethod
    def encode_message(message: BaseMessage) -> bytes:
        json_str = message.model_dump_json()
        return json_str.encode(cp.ENCODING)

    @staticmethod
    def decode_message(data: bytes) -> MessageUnion:
        json_str = data.decode(cp.ENCODING)
        return _message_adapter.validate_json(json_str)

    @staticmethod
    def encode_data(metadata: MetaData, binary_data: bytes) -> bytes:
        metadata_bytes = DSerial.encode_message(metadata)
        return DSerial.add_head(metadata_bytes) + binary_data

    @staticmethod
    def decode_data(data: bytes) -> Tuple[MetaData, bytes]:
        size, chunk = DSerial.split_head(data)
        metadata = DSerial.decode_message(chunk[:size])
        return metadata, chunk[size:]


# Bind DSerial to the concrete class for runtime use
DSerial = DataSerialize
