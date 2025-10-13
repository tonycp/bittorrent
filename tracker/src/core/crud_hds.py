from typing import Callable, Any, Dict, Optional
from .bsc_hds import create_handler


def create(
    dataset: Dict[str, Optional[Callable[[Any], bool]]],
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    return create_handler("Create", dataset)


def update(
    dataset: Dict[str, Optional[Callable[[Any], bool]]],
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    return create_handler("Update", dataset)


def delete(
    dataset: Dict[str, Optional[Callable[[Any], bool]]],
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    return create_handler("Delete", dataset)


def get(
    dataset: Dict[str, Optional[Callable[[Any], bool]]],
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    return create_handler("Get", dataset)


def get_all(
    dataset: Dict[str, Optional[Callable[[Any], bool]]],
) -> Callable[[Callable[..., Any]], Callable[..., str]]:
    return create_handler("GetAll", dataset)
