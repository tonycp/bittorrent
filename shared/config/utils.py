from typing import Any, Callable, Dict
from functools import lru_cache

__all__ = ["get_default_settings"]


def _only_default(_, y):
    return y


@lru_cache
def _get_constants(module):
    return {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper() and not name.startswith("__")
    }


def get_default_settings(
    settings: Dict[str, Any],
    module_key,
    module_const,
    func: Callable[[str], str] = _only_default,
):
    getenv_map = {}
    env_key = _get_constants(module_key)
    env_default = _get_constants(module_const)

    for key, value in env_key.items():
        default = env_default.get(f"DEFAULT_{key}")
        trans = func(value, default)
        getenv_map[value] = settings.get(key, trans)

    return getenv_map
