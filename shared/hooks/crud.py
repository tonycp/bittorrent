from shared.models.typing import Handler, HdlDec
from shared.const import c_crud as cc

from .hook import create_decorator
from ._process import create_hook

__all__ = [
    "create",
    "update",
    "delete",
    "get",
    "get_all",
]


def create(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.CREATE, transform)


def update(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.UPDATE, transform)


def delete(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.DELETE, transform)


def get(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.GET, transform)


def get_all(transform: Handler = create_hook) -> HdlDec:
    return create_decorator(cc.GETALL, transform)
