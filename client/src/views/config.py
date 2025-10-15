import configparser
import os


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
        self.config["General"] = {
            "download_path": "./downloads",
            "listen_port": "6881",
            "max_download_rate": "0",
            "max_upload_rate": "0",
            "max_connections": "200",
        }

    def save_config(self):
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def get(self, section, key):
        try:
            return self.config.get(section, key)
        except:
            return None

    def set(self, section, key, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        self.save_config()

    def get_download_path(self):
        return self.get("General", "download_path")

    def get_listen_port(self):
        value = self.get("General", "listen_port")
        return int(value) if value else 6881

    def get_max_download_rate(self):
        value = self.get("General", "max_download_rate")
        return int(value) if value else 0

    def get_max_upload_rate(self):
        value = self.get("General", "max_upload_rate")
        return int(value) if value else 0

    def get_max_connections(self):
        value = self.get("General", "max_connections")
        return int(value) if value else 200
