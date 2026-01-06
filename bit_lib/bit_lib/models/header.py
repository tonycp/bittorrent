from typing import (
    Any,
    Dict,
    List,
    Tuple,
)

from dataclass_mapper import map_to, mapper_from
from dataclasses import dataclass

from .message import Request


def get_args(request: Request):
    return list(request.args.keys())


def gen_index(*args):
    return str.join("//", args)


@mapper_from(Request, {"args": get_args})
@dataclass
class Header:
    controller: str
    command: str
    func: str
    args: List[str]


def decode_request(request: Request) -> Tuple[Header, Dict[str, Any]]:
    try:
        return map_to(request, Header), request.args
    except Exception as e:
        raise ValueError("Invalid request format") from e


def process_header(header: Header):
    if not (header.command and header.func):
        raise ValueError("Missing command or func in header")
    endpoint = header.controller or ""
    args = ":?".join(header.args) + ":?"
    return endpoint, gen_index(header.command, header.func, args)
