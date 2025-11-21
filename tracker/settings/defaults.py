from typing import Any, Dict
from shared.context.defaults import get_default_settings

from tracker.const import c_env
from tracker.const import k_env


def get_settings(settings: Dict[str, Any] = {}) -> Dict[str, Any]:
    return get_default_settings(settings, k_env, c_env)
