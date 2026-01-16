from pydantic import (
    StrictInt,
    StrictStr,
)

FILE_INFO_DATASET = {
    "info_hash": StrictStr,
}

CREATE_TORRENT_DATASET = {
    "info_hash": StrictStr,
    "file_name": StrictStr,
    "file_size": StrictInt,
    "total_chunks": StrictInt,
    "piece_length": StrictInt,
}
