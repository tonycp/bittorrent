"""Handler base para operaciones de mantenimiento"""

from abc import ABC, abstractmethod

from bit_lib.handlers.hander import BaseHandler
from bit_lib.models import Response


class BaseMaintenanceHandler(BaseHandler, ABC):
    """Handler base abstracto para operaciones de mantenimiento"""

    @abstractmethod
    async def cleanup_peers(self, max_inactive_minutes: int) -> dict:
        """Limpia peers inactivos"""
        pass

    @abstractmethod
    async def cleanup_torrents(self) -> dict:
        """Limpia torrents huérfanos"""
        pass

    @abstractmethod
    async def cleanup_events(self, retention_minutes: int) -> dict:
        """Limpia eventos antiguos"""
        pass

    @abstractmethod
    async def remove_dead_trackers(self, ttl_minutes: int) -> dict:
        """Limpia trackers muertos del registro"""
        pass

    async def dispatch(self, hdl_key: str, data: dict, msg_id: str) -> Response:
        """Despacha request y retorna Response (implementado por BaseHandler.process)"""
        return await self.process(hdl_key, data, msg_id)
