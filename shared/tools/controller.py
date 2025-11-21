from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Type


def controller(endpoint: str = None):
    def decorator(cls):
        cls.endpoint = endpoint or cls.endpoint
        return cls

    return decorator


class ControllerMeta(ABCMeta):
    controllers: Dict[str, Type] = {}
    endpoint: str = None

    def __init__(cls, name, bases, namespace):
        cls.endpoint = name
        super().__init__(name, bases, namespace)
        cls.controllers[name] = cls


class BaseController(ABC, metaclass=ControllerMeta):
    @abstractmethod
    async def process(self, ctrl_key: str, *args, **kwargs):
        pass
