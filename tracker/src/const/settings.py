from os import getenv
from typing import Any, Dict
from .env import DB_URL


def get_settings() -> Dict[str, Any]:
    db_url = getenv(DB_URL, "sqlite:///tracker.db")
    return {
        DB_URL: db_url,
    }
