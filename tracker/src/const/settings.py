from os import getenv
from typing import Any, Dict

from .default import *
from .env import *


def get_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    getenv_map = {
        DB_URL: getenv(DB_URL, DEFAULT_DB),
        TRK_HOST: getenv(TRK_HOST, DEFAULT_TRK_HOST),
        TRK_PORT: getenv(TRK_PORT, DEFAULT_TRK_PORT),
    }

    for key, value in settings.items():
        if value is not None:
            getenv_map[key] = value

    return getenv_map
