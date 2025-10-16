from functools import lru_cache

from os import getenv
from typing import Any, Callable, Dict

from ..const import env as e_const
from ..const import default as d_const
from ..const import config as c_const


@lru_cache
def _get_constants(module):
    return {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper() and not name.startswith("__")
    }


def _get_default_settings(
    settings: Dict[str, Any],
    module_key,
    func: Callable[[str], str] = lambda _, y: y,
):
    getenv_map = {}
    env_key = _get_constants(module_key)
    env_default = _get_constants(d_const)

    for key, value in env_key.items():
        default = env_default.get(f"DEFAULT_{key}")
        trans = func(value, default)
        getenv_map[value] = settings.get(key, trans)

    return getenv_map


def get_settings(settings: Dict[str, Any] = {}) -> Dict[str, str]:
    return _get_default_settings(settings, c_const)


def get_env_settings(settings: Dict[str, Any] = {}) -> Dict[str, Any]:
    return _get_default_settings(settings, e_const, getenv)
