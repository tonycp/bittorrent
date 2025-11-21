from dataclasses import dataclass


@dataclass
class BaseMessage:
    msg_id: str
    timestamp: int
    version: str
