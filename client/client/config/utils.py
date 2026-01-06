from os import getenv
from typing import Any, Dict
from shared import get_default_settings
from const import (
    env as e_const,
    default as d_const,
    config as c_const,
)

__all__ = [
    "get_settings",
    "get_env_settings",
]


def get_settings(settings: Dict[str, Any] = {}) -> Dict[str, str]:
    return get_default_settings(settings, c_const, d_const)


def get_env_settings(settings: Dict[str, Any] = {}) -> Dict[str, Any]:
    return get_default_settings(settings, e_const, d_const, getenv)
