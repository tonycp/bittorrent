from typing import Callable, Any, Dict, Optional, Tuple, Type

import json

__all__ = ["controller", "create_handler"]

_controllers: Dict[
    str,
    str,
] = {}

_handlers: Dict[
    str,
    Tuple[
        Callable[[Dict[str, Any]], str],
        Dict[str, Callable[[Any], bool]],
    ],
] = {}


def controller(endpoint_name: Optional[str] = None) -> Type[Any]:
    """Class decorator to mark a class as a controller."""
    global _controllers

    def cls_decorator(cls: Type[Any]) -> Type[Any]:
        nonlocal endpoint_name
        endpoint_name = endpoint_name or cls.__name__
        _controllers[endpoint_name] = cls.__name__
        return cls

    return cls_decorator


def create_handler(
    command_name: str, dataset: Dict[str, Callable[[Any], bool]]
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    """Generic handler factory for commands within a controller."""
    global _handlers

    def handler(func: Callable[..., Any]) -> Callable[..., str]:
        args = ":?".join(dataset.keys()) + ":?"
        is_class = is_method_class(func)
        class_name = ""
        is_static = False

        if is_class:
            class_name = func.__qualname__.split(".")[0]
            is_static = is_static_method(func, class_name)

        index = f"{class_name}//{command_name}//{func.__name__}//{args}"

        def wrapper(data: Dict[str, Any], instance: Any = None) -> str:
            contains_self = is_class and not is_static
            result = func(instance, **data) if (contains_self) else func(**data)
            return json.dumps(result)

        # Register the handler at decoration time
        _handlers[index] = (wrapper, dataset, is_class)

        return wrapper

    return handler


def is_method_class(func: Callable[..., Any]) -> bool:
    return hasattr(func, "__qualname__") and "." in func.__qualname__


def is_static_method(func: Callable[..., Any], class_name: str) -> bool:
    cls = func.__globals__.get(class_name)
    if cls is None:
        return False
    for cls_ in cls.__mro__:
        if func.__name__ in cls_.__dict__:
            return isinstance(cls_.__dict__[func.__name__], staticmethod)
    return False
