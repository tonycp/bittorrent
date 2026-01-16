import configparser
import os
from pathlib import Path
from typing import Optional

from src.client.const.config import (
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


class ConfigManager:
    def __init__(self, config_file: Optional[str] = None):
        if config_file is None:
            config_dir = Path.home() / ".config" / "bittorrent"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = str(config_dir / "config.ini")
        
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        if os.path.exists(config_file):
            self.config.read(config_file)
        else:
            self.set_defaults()
            self.save()

    def set_defaults(self):
        """Set default configuration values"""
        defaults = {
            DL_PATH: str(Path.home() / "Downloads" / "bittorrent"),
            TN_PATH: str(Path.home() / ".local" / "share" / "bittorrent" / "torrents"),
            TK_URL: "http://localhost:5555",
            LT_PORT: "6881",
            MAX_DL_RATE: "0",
            MAX_UL_RATE: "0",
            MAX_CON: "50",
        }
        
        for key in set(sections.values()):
            if not self.config.has_section(key):
                self.config.add_section(key)
        
        for key, value in defaults.items():
            sec = sections.get(key, GENERAL)
            if not self.config.has_section(sec):
                self.config.add_section(sec)
            self.config.set(sec, key, str(value))

    def get(self, section: str, key: str) -> str:
        """Get a configuration value"""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return ""
    
    def set(self, section: str, key: str, value: str):
        """Set a configuration value"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def save_config(self):
        """Alias for save()"""
        self.save()

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
