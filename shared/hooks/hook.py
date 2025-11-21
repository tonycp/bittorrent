from typing import Dict

from shared.models.typing import Controller, Handler, HdlDec, Hook
from shared.tools import Descriptor, BaseController, ControllerMeta


def create_decorator(command: str, transform: Handler) -> HdlDec:
    def decorator(func: Controller) -> Hook:
        return HookDescriptor(command, func, transform)

    return decorator


class HookDescriptor(Descriptor):
    def __init__(self, command, func, transform):
        super().__init__(command, func)
        self.transform = transform

    def setup(self, owner: "BaseHook", name: str):
        self.transform = self.transform(owner.__name__, self.command, name)

    def register(self, owner: "BaseHook", index: str, wrapper: Handler):
        owner.hooks[index] = wrapper


class HookMeta(ControllerMeta):
    hooks: Dict[str, Hook]

    def __new__(cls, name, bases, namespace):
        cls.hooks = {}
        return super().__new__(cls, name, bases, namespace)


class BaseHook(BaseController, metaclass=HookMeta):
    @classmethod
    def get_hook(cls, sub_key):
        return cls.hooks.get(sub_key)

    async def process(self, hdl_key: str):
        hook = self.get_hook(hdl_key)
        return hook(self)
