from os import getenv
from typing import Any, Dict

from .env_def import *
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

# import bencodepy
# import hashlib


# def load_torrent(filepath):
#     # Leer y decodificar .torrent
#     with open(filepath, "rb") as f:
#         torrent_data = bencodepy.decode(f.read())
#     info = torrent_data[b"info"]
#     name = info[b"name"]
#     if isinstance(name, bytes):
#         name = name.decode()
#     info_encoded = bencodepy.encode(info)
#     info_hash = hashlib.sha1(info_encoded).hexdigest()
#     return get_torrent_info_template(info_hash, name)