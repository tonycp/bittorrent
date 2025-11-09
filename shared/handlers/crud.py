from shared.interface.typing import DataSet, HdlDecorator
from shared.const import c_crud as cc

from .hander import create_decorator

__all__ = [
    "create",
    "update",
    "delete",
    "get",
    "get_all",
]


def create(dataset: DataSet) -> HdlDecorator:
    return create_decorator(cc.CREATE, dataset)


def update(dataset: DataSet) -> HdlDecorator:
    return create_decorator(cc.UPDATE, dataset)


def delete(dataset: DataSet) -> HdlDecorator:
    return create_decorator(cc.DELETE, dataset)


def get(dataset: DataSet) -> HdlDecorator:
    return create_decorator(cc.GET, dataset)


def get_all(dataset: DataSet) -> HdlDecorator:
    return create_decorator(cc.GETALL, dataset)
