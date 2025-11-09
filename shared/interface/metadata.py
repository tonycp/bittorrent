from dataclasses import dataclass
from .message import BaseMessage


@dataclass
class MetaData(BaseMessage):
    hash: str
    index: int
