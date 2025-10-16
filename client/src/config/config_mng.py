# bittorrent_client/config/config_manager.py
import configparser
import os

from .utils import get_settings
from ..const.config import *


class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.set_defaults()
            self.save_config()

    def set_defaults(self):
        settings = get_settings()
        for key in set(sections.values()):
            if not self.config.has_section(key):
                self.config.add_section(key)
        for key, value in settings.items():
            sec = sections.get(key, GENERAL)
            if not self.config.has_section(sec):
                self.config.add_section(sec)
            self.config.set(sec, key, str(value))

    def save_config(self):
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def get(self, section, key):
        try:
            return self.config.get(section, key)
        except Exception:
            return None

    def set(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        self.save_config()

    def get_general(self, key):
        return self.get(GENERAL, key)

    def set_general(self, key, value):
        self.config.set(GENERAL, key, str(value))
        self.save_config()

    # Métodos helper para uso directo:
    def get_download_path(self):
        return self.get(GENERAL, DL_PATH)

    def get_torrent_path(self):
        return self.get(GENERAL, TN_PATH)

    def get_tracker_address(self):
        ip, port = self.get(GENERAL, TK_URL).split(":")
        return ip, int(port)

    def get_listen_port(self):
        value = self.get(GENERAL, LT_PORT)
        return int(value) if value else 6881

    def get_max_download_rate(self):
        value = self.get(GENERAL, MAX_DL_RATE)
        return int(value) if value else 0

    def get_max_upload_rate(self):
        value = self.get(GENERAL, MAX_UL_RATE)
        return int(value) if value else 0

    def get_max_connections(self):
        value = self.get(GENERAL, MAX_CON)
        return int(value) if value else 200
