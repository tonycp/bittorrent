from typing import Type
from abc import ABC, abstractmethod
from shared.models.typing import Controller, Handler

from .subscribe import create_wrapper, get_index_sub
from .controller import BaseController


class Descriptor(ABC):
    _transform: Handler

    def __init__(self, command: str, func: Controller, id: str = None):
        self.command = func.command = command
        self.transform = None
        self.func = func
        self.id = id

    def __get__(self, instance: BaseController, owner: Type[BaseController]):
        if instance is None:
            return self.func
        return self.func.__get__(instance, owner)

    def setup(self, owner: Type[BaseController], name: str):
        pass

    @abstractmethod
    def register(self, owner: Type[BaseController], index: str, wrapper: Handler):
        pass

    def __set_name__(self, owner: Type[BaseController], name: str):
        self.setup(owner, name)
        index, wrapper = self._gen_wrapper(name)
        self.register(owner, index, wrapper)

    def _gen_wrapper(self, method_name: str):
        wrapper = create_wrapper(self.func, self.transform)
        index = get_index_sub(self.command, method_name, self.id)
        return index, wrapper

    @property
    def transform(self):
        return self._transform

    @transform.setter
    def transform(self, transform):
        self._transform = transform
