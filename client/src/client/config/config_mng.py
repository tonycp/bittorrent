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
        # Siempre usar /app para entorno Docker
        defaults = {
            DL_PATH: "/app/downloads",
            TN_PATH: "/app/torrents",
            TK_URL: "tracker-1:5555",
            LT_PORT: "6881",
            MAX_DL_RATE: "0",
            MAX_UL_RATE: "0",
            MAX_CON: "50",
            "tracker_health_interval": "30",
            "tracker_discovery_interval": "60",
            "tracker_discovery_enabled": "true",
        }
        
        # Forzar valores correctos incluso si el archivo existe
        for key, value in defaults.items():
            sec = sections.get(key, GENERAL)
            if not self.config.has_section(sec):
                self.config.add_section(sec)
            # Sobrescribir siempre las rutas para asegurar /app
            if key in [DL_PATH, TN_PATH]:
                self.config.set(sec, key, value)
        
        # Asegurar que existen todas las secciones
        for key in set(sections.values()):
            if not self.config.has_section(key):
                self.config.add_section(key)
        
        # Aplicar valores por defecto solo si no existen
        for key, value in defaults.items():
            sec = sections.get(key, GENERAL)
            if not self.config.has_section(sec):
                self.config.add_section(sec)
            # Solo escribir si no existe (excepto rutas que ya se forzaron arriba)
            if key not in [DL_PATH, TN_PATH] and not self.config.has_option(sec, key):
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
        """Retorna (ip, port) desde tracker_address, manejando formato URL"""
        addr = self.get(GENERAL, TK_URL)
        # Remover protocolo si existe (http://, https://)
        if "://" in addr:
            addr = addr.split("://")[1]
        # Separar ip:puerto
        if ":" in addr:
            ip, port = addr.split(":")
            return ip, int(port)
        # Si no hay puerto, usar default
        return addr, 5555

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
