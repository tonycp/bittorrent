from bit_lib.const import c_proto as cp

from pydantic import BaseModel, Field
from typing import (
    Literal,
    Optional,
    Union,
)

from .typing import Data

import time
import uuid


def _get_msg_uuid() -> str:
    return f"msg_{uuid.uuid4().hex[:8]}"


class BaseMessage(BaseModel):
    type: str = Field(discriminator=True)

    version: str = cp.PROTOCOL_VERSION
    msg_id: str = Field(default_factory=_get_msg_uuid)
    timestamp: int = Field(default_factory=time.time_ns)


class MetaData(BaseMessage):
    type: Literal["metadata"] = "metadata"

    hash: str
    index: int


class Response(BaseMessage):
    type: Literal["response"] = "response"

    reply_to: str
    data: Optional[Data] = None


class Error(Response):
    type: Literal["error"] = "error"


class Request(BaseMessage):
    type: Literal["request"] = "request"

    controller: str
    command: str
    func: str
    args: Optional[Data] = None

    def build_response(self, data: Optional[Data] = None) -> "Response":
        return Response(reply_to=self.msg_id, data=data)

    def build_error(self, data: Optional[Data] = None) -> "Error":
        return Error(reply_to=self.msg_id, data=data)


MessageUnion = Union[Request, Response, Error]
