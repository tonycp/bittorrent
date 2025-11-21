from typing import Dict, Type
from shared.tools import Descriptor, BaseController, ControllerMeta
from shared.models.typing import (
    Controller,
    Data,
    DataSet,
    Handler,
    HdlDec,
    HdlInfo,
)

from ._process import _models_validate, _names_validate


def create_decorator(command: str, dataset: DataSet) -> HdlDec:
    def decorator(func: Controller) -> Handler:
        return HandleDescriptor(command, func, dataset)

    return decorator


class HandleDescriptor(Descriptor):
    def __init__(self, command: str, func: Controller, dataset: DataSet):
        count = func.__code__.co_argcount
        args = func.__code__.co_varnames[1:count]
        keys = set(dataset.keys())
        names = set(args)

        _names_validate(func, names, keys)

        id = ", ".join(f"{arg}:?" for arg in args)
        super().__init__(command, func, id)

        self.dataset = dataset

    def register(self, owner: Type["BaseHandler"], index: str, wrapper: Handler):
        owner._handlers[index] = (wrapper, self.dataset)


class HandlerMeta(ControllerMeta):
    _handlers: Dict[str, HdlInfo] = None

    def __new__(cls, name, bases, namespace):
        return super().__new__(cls, name, bases, namespace)

    def __init__(cls, name, bases, namespace):
        cls._handlers = cls._handlers or {}
        super().__init__(name, bases, namespace)


class BaseHandler(BaseController, metaclass=HandlerMeta):
    @classmethod
    def get_handler(cls, sub_key: str) -> HdlInfo:
        return cls._handlers.get(sub_key)

    async def process(self, hdl_key: str, data: Data):
        handler, dataset = self.get_handler(hdl_key)
        return await handler(self, _models_validate(handler.__name__, data, dataset))
