from pyparsing import abstractmethod
from abc import ABCMeta

import configparser
import os

__all__ = ["ABConfigManager"]


class ABConfigManager(metaclass=ABCMeta):
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

    @abstractmethod
    def set_defaults(self):
        pass

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
