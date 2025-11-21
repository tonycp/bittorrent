from typing import Callable, Optional, Type
from shared.models.typing import Controller, Handler, Data

__all__ = ["create_wrapper", "get_index_sub"]


def is_static_method(func: Controller, class_name: str) -> bool:
    cls = func.__globals__.get(class_name)
    if cls is None:
        return False
    for cls_ in cls.__mro__:
        if func.__name__ in cls_.__dict__:
            return isinstance(cls_.__dict__[func.__name__], staticmethod)
    return False


def gen_index(*args):
    return str.join("//", args)


def get_index_sub(command, name, id=""):
    return gen_index(command, name, id)


def create_wrapper(
    func: Handler,
    transform: Optional[Handler],
) -> Callable[..., str]:
    def wrapper(instance: Type, data: Data) -> str:
        is_static = True
        if instance:
            cls = instance.__class__.__name__
            is_static = is_static_method(func, cls)
        result = func(**data) if (is_static) else func(instance, **data)
        return transform(result) if transform else result

    return wrapper
