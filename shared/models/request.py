from shared.models.message import BaseMessage

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Request(BaseMessage):
    controller: str
    command: str
    func: str
    args: Dict[str, Any]
