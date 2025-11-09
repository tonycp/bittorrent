from typing import Dict, Type


def controller(endpoint: str = None):
    def decorator(cls: "BaseController"):
        cls.endpoint = endpoint or cls.__name__
        return cls

    return decorator


class ControllerMeta(type):
    controllers: Dict[str, Type] = {}
    endpoint: str

    def __new__(cls, name, bases, namespace):
        cls.endpoint = cls.endpoint or cls.__name__
        return super().__new__(cls, name, bases, namespace)

    def __init__(cls, nombre, bases, namespace):
        super().__init__(nombre, bases, namespace)
        cls.controllers[nombre] = cls


class BaseController(metaclass=ControllerMeta):
    @classmethod
    def get_endpoint(cls) -> str:
        return cls.endpoint
    
    def process(self, ctrl_key: str, *args, **kwargs) -> str:
        pass