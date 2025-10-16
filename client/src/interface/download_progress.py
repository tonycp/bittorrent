from dataclasses import dataclass


@dataclass
class DownloadProgress:
    file_name: str
    file_size: int
    downloaded_size: int
    progress: int
    downloaded_chunks: int
    total_chunks: int
