from shared import ABConfigManager
from utils import get_settings
from const.config import (
    sections,
    GENERAL,
    DL_PATH,
    TN_PATH,
    TK_URL,
    LT_PORT,
    MAX_DL_RATE,
    MAX_UL_RATE,
    MAX_CON,
)


class ConfigManager(ABConfigManager):
    def __init__(self, config_file="config.ini"):
        super().__init__(config_file)

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
