from typing import Optional, Tuple, TypeAlias, Union
from shared.interface import MetaData, BaseMessage, Request
from shared.interface.typing import Data
from shared.const import c_proto as cp

import json
import time
import uuid

dts: TypeAlias = "DataSerialize"


def _get_msg_uuid():
    return f"msg_{uuid.uuid4().hex[:8]}"


def _fill_base_message(base: BaseMessage, msg_id: Optional[str] = None):
    base.msg_id = msg_id or _get_msg_uuid()
    base.timestamp = int(time.time())
    base.version = DataSerialize.VERSION


class DataSerialize:
    VERSION = "2.0"

    @staticmethod
    def add_size(data: bytes) -> bytes:
        head = len(data).to_bytes(cp.SIZE_HEAD, cp.BYTEORDER)
        return head + data

    @staticmethod
    def split_size(msg: bytes) -> Tuple[int, bytes]:
        if len(msg) < cp.SIZE_HEAD:
            return 0, msg
        head = msg[: cp.SIZE_HEAD]
        data = msg[cp.SIZE_HEAD :]
        size = int.from_bytes(head, cp.BYTEORDER)
        return size, data

    @staticmethod
    def encode_message(message: Request) -> bytes:
        json_str = json.dumps(message)
        return json_str.encode(cp.ENCODING)

    @staticmethod
    def decode_message(data: bytes, in_data: bool = True) -> Union[Request, Data]:
        json_str = data.decode(cp.ENCODING)
        kwargs = json.loads(json_str)
        return Request(**kwargs) if in_data else kwargs

    @staticmethod
    def encode_data(metadata: MetaData, binary_data: bytes) -> bytes:
        metadata_json = dts.encode_message(metadata)
        return dts.add_size(metadata_json) + binary_data

    @staticmethod
    def decode_data(
        data: bytes, in_data: bool = True
    ) -> Tuple[Union[MetaData, Data], bytes]:
        size, chunk = dts.split_size(data)
        kwargs = dts.decode_message(chunk[:size], False)
        metadata = MetaData(**kwargs) if in_data else kwargs
        return metadata, chunk[size:]

    @staticmethod
    def decode(data: bytes, msg_type: int, in_data: bool = True):
        if msg_type == cp.MSG_TYPE_JSON:
            return dts.decode_message(data, in_data)
        return dts.decode_data(data, in_data)

    @staticmethod
    def create_message(
        controller: str,
        command: str,
        func: str,
        args: Optional[Data] = None,
        msg_id: Optional[str] = None,
    ) -> Request:
        header = Request(
            controller=controller,
            command=command,
            func=func,
            args=args,
        )
        _fill_base_message(header, msg_id)
        return header

    @staticmethod
    def create_metadata(
        hash: str,
        index: int,
        msg_id: Optional[str] = None,
    ) -> MetaData:
        metadata = MetaData(
            hash=hash,
            index=index,
        )
        _fill_base_message(metadata, msg_id)
        return metadata
