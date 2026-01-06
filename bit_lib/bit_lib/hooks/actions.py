from bit_lib.const import c_commands as cc
from bit_lib.models import (
    Handler,
    HdlDec,
)

from .hook import create_decorator
from ._process import create_hook

__all__ = [
    "send_command",
    "send_data",
    "request_data",
]


def send_command(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.CREATE, transform)


def send_data(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.UPDATE, transform)


def request_data(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.DELETE, transform)
