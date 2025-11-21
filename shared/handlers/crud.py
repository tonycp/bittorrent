from shared.models.typing import DataSet, HdlDec
from shared.const import c_crud as cc

from .hander import create_decorator

__all__ = [
    "create",
    "update",
    "delete",
    "get",
    "get_all",
]


def create(dataset: DataSet) -> HdlDec:
    return create_decorator(cc.CREATE, dataset)


def update(dataset: DataSet) -> HdlDec:
    return create_decorator(cc.UPDATE, dataset)


def delete(dataset: DataSet) -> HdlDec:
    return create_decorator(cc.DELETE, dataset)


def get(dataset: DataSet) -> HdlDec:
    return create_decorator(cc.GET, dataset)


def get_all(dataset: DataSet) -> HdlDec:
    return create_decorator(cc.GETALL, dataset)
