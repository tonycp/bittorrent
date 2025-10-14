import copy

from .crud_tmp import *
from .bsc_tmp import set_data_template

TORRENT_INFO = {
    "info_hash": "[INFO_HASH]",
    "name": "[NAME]",
    "estado": "Nuevo",
    "progreso": 0,
}


def get_torrent_info_template(info_hash, name):
    template = copy.deepcopy(TORRENT_INFO)
    template["info_hash"] = info_hash
    template["name"] = name
    return template
