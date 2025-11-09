from typing import Dict
from shared.tools import Descriptor, BaseController, ControllerMeta
from shared.interface.typing import (
    Controller,
    Data,
    DataSet,
    Handler,
    HdlDecorator,
    HdlInfo,
)

from ._process import load_data


def create_decorator(command: str, dataset: DataSet) -> HdlDecorator:
    def decorator(func: Controller) -> Handler:
        return HandleDescriptor(command, func, dataset)

    return decorator


class HandleDescriptor(Descriptor):
    def __init__(self, command: str, func: Controller, dataset: DataSet):
        args = ":?".join(self.dataset.keys()) + ":?"
        super().__init__(command, func, args)
        self.dataset = dataset

    def register(self, owner: "BaseHandler", index: str, wrapper: Handler):
        owner._handlers[index] = (wrapper, self.dataset)


class HandlerMeta(ControllerMeta):
    _handlers: Dict[str, HdlInfo]

    def __new__(cls, name, bases, namespace):
        cls._handlers = {}
        return super().__new__(cls, name, bases, namespace)


class BaseHandler(BaseController, metaclass=HandlerMeta):
    @classmethod
    def get_handler(cls, sub_key):
        return cls._handlers.get(sub_key)

    def process(self, hdl_key: str, data: Data) -> str:
        handler, dataset = self.get_handler(hdl_key)
        return handler(self, load_data(data, dataset))
