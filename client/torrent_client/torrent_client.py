import libtorrent as lt
import time
import os


class TorrentClient:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.session = lt.session()
        self.handles = []
        self.setup_session()

    def setup_session(self):
        settings = {
            "listen_interfaces": f"0.0.0.0:{self.config_manager.get_listen_port()}",
            "enable_dht": True,
            "enable_lsd": True,
            "enable_upnp": True,
            "enable_natpmp": True,
        }

        self.session.apply_settings(settings)

        download_limit = self.config_manager.get_max_download_rate()
        upload_limit = self.config_manager.get_max_upload_rate()

        if download_limit > 0:
            self.session.set_download_rate_limit(download_limit * 1024)

        if upload_limit > 0:
            self.session.set_upload_rate_limit(upload_limit * 1024)

    def add_torrent(self, torrent_path):
        info = lt.torrent_info(torrent_path)

        params = {"ti": info, "save_path": self.config_manager.get_download_path()}

        handle = self.session.add_torrent(params)
        self.handles.append(handle)

        return handle

    def get_torrent_info(self, torrent_path):
        info = lt.torrent_info(torrent_path)

        torrent_data = {
            "name": info.name(),
            "total_size": info.total_size(),
            "num_files": info.num_files(),
            "files": [],
        }

        for i in range(info.num_files()):
            file_info = info.files().at(i)
            torrent_data["files"].append(
                {"path": file_info.path, "size": file_info.size}
            )

        return torrent_data

    def get_status(self, handle):
        status = handle.status()

        return {
            "name": status.name,
            "progress": status.progress * 100,
            "download_rate": status.download_rate / 1024,
            "upload_rate": status.upload_rate / 1024,
            "num_peers": status.num_peers,
            "num_seeds": status.num_seeds,
            "state": str(status.state),
            "total_download": status.total_download,
            "total_upload": status.total_upload,
        }

    def get_all_torrents(self):
        return self.handles

    def pause_torrent(self, handle):
        handle.pause()

    def resume_torrent(self, handle):
        handle.resume()

    def remove_torrent(self, handle):
        self.session.remove_torrent(handle)
        if handle in self.handles:
            self.handles.remove(handle)
