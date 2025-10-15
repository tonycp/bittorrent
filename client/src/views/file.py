import os
import hashlib
import json


class FileManager:
    CHUNK_SIZE = 256 * 1024

    def __init__(self, download_path):
        self.download_path = download_path
        self.files = {}
        self.active_downloads = {}

    @staticmethod
    def calculate_file_hash(file_path):
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(FileManager.CHUNK_SIZE)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def calculate_chunk_hash(data):
        return hashlib.sha256(data).hexdigest()

    def create_torrent_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        file_size = os.path.getsize(file_path)
        file_hash = self.calculate_file_hash(file_path)
        file_name = os.path.basename(file_path)

        total_chunks = (file_size + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE

        chunks_info = []
        with open(file_path, "rb") as f:
            for i in range(total_chunks):
                chunk_data = f.read(self.CHUNK_SIZE)
                chunk_hash = self.calculate_chunk_hash(chunk_data)
                chunks_info.append(
                    {"id": i, "size": len(chunk_data), "hash": chunk_hash}
                )

        torrent_data = {
            "file_name": file_name,
            "file_size": file_size,
            "file_hash": file_hash,
            "chunk_size": self.CHUNK_SIZE,
            "total_chunks": total_chunks,
            "chunks": chunks_info,
        }

        torrent_file = f"{file_path}.p2p"
        with open(torrent_file, "w") as f:
            json.dump(torrent_data, f, indent=2)

        return torrent_file, torrent_data

    def load_torrent_file(self, torrent_path):
        with open(torrent_path, "r") as f:
            torrent_data = json.load(f)

        file_hash = torrent_data["file_hash"]
        self.files[file_hash] = torrent_data

        return torrent_data

    def get_chunk(self, file_path, chunk_id):
        try:
            with open(file_path, "rb") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                chunk_data = f.read(self.CHUNK_SIZE)
                return chunk_data
        except Exception as e:
            print(f"Error leyendo chunk {chunk_id}: {e}")
            return None

    def write_chunk(self, file_hash, chunk_id, chunk_data):
        if file_hash not in self.active_downloads:
            return False

        download = self.active_downloads[file_hash]
        file_path = download["file_path"]

        try:
            with open(file_path, "r+b") as f:
                f.seek(chunk_id * self.CHUNK_SIZE)
                f.write(chunk_data)

            download["downloaded_chunks"].add(chunk_id)
            download["downloaded_size"] += len(chunk_data)

            return True
        except Exception as e:
            print(f"Error escribiendo chunk {chunk_id}: {e}")
            return False

    def start_download(self, torrent_data):
        file_hash = torrent_data["file_hash"]
        file_name = torrent_data["file_name"]
        file_size = torrent_data["file_size"]
        total_chunks = torrent_data["total_chunks"]

        file_path = os.path.join(self.download_path, file_name)

        with open(file_path, "wb") as f:
            f.seek(file_size - 1)
            f.write(b"\0")

        self.active_downloads[file_hash] = {
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "total_chunks": total_chunks,
            "downloaded_chunks": set(),
            "downloaded_size": 0,
            "torrent_data": torrent_data,
        }

        return file_hash

    def get_download_progress(self, file_hash):
        if file_hash not in self.active_downloads:
            return None

        download = self.active_downloads[file_hash]
        progress = len(download["downloaded_chunks"]) / download["total_chunks"] * 100

        return {
            "file_name": download["file_name"],
            "file_size": download["file_size"],
            "downloaded_size": download["downloaded_size"],
            "progress": progress,
            "downloaded_chunks": len(download["downloaded_chunks"]),
            "total_chunks": download["total_chunks"],
        }

    def get_missing_chunks(self, file_hash):
        if file_hash not in self.active_downloads:
            return []

        download = self.active_downloads[file_hash]
        all_chunks = set(range(download["total_chunks"]))
        missing = all_chunks - download["downloaded_chunks"]

        return list(missing)

    def is_download_complete(self, file_hash):
        if file_hash not in self.active_downloads:
            return False

        download = self.active_downloads[file_hash]
        return len(download["downloaded_chunks"]) == download["total_chunks"]
