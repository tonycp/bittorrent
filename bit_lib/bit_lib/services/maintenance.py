"""Servicio remoto para operaciones de mantenimiento"""

import logging

from bit_lib.handlers.maintenance import BaseMaintenanceHandler
from bit_lib.services._client import ClientService
from bit_lib.models import Request, Response

logger = logging.getLogger(__name__)


class RemoteMaintenance(BaseMaintenanceHandler, ClientService):
    """Implementación remota: envía RPC a través de la red"""

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port

    async def dispatch(self, hdl_key: str, data: dict, msg_id: str) -> Response:
        """Despacha request remoto vía RPC"""
        try:
            parts = hdl_key.split(":")
            if len(parts) < 3:
                logger.warning(f"Invalid hdl_key format: {hdl_key}")
                return None

            req = Request(
                controller=parts[0],
                command=parts[1],
                func=parts[2],
                data=data,
            )
            resp = await self.request(self.host, self.port, req, timeout=5.0)
            if resp:
                resp.reply_to = msg_id
            return resp
        except Exception as e:
            logger.error(f"Error in remote dispatch: {e}")
            return None

    async def cleanup_peers(self, max_inactive_minutes: int) -> dict:
        """Limpia peers inactivos vía RPC remoto"""
        try:
            resp = await self.dispatch(
                "Maintenance:update:cleanup_peers",
                {"max_inactive_minutes": max_inactive_minutes},
                "cleanup_peers",
            )
            return resp.data if resp else {}
        except Exception as e:
            logger.error(f"Error in remote cleanup_peers: {e}")
            return {}

    async def cleanup_torrents(self) -> dict:
        """Limpia torrents huérfanos vía RPC remoto"""
        try:
            resp = await self.dispatch(
                "Maintenance:update:cleanup_torrents",
                {},
                "cleanup_torrents",
            )
            return resp.data if resp else {}
        except Exception as e:
            logger.error(f"Error in remote cleanup_torrents: {e}")
            return {}

    async def cleanup_events(self, retention_minutes: int) -> dict:
        """Limpia eventos antiguos vía RPC remoto"""
        try:
            resp = await self.dispatch(
                "Maintenance:update:cleanup_events",
                {"retention_minutes": retention_minutes},
                "cleanup_events",
            )
            return resp.data if resp else {}
        except Exception as e:
            logger.error(f"Error in remote cleanup_events: {e}")
            return {}

    async def remove_dead_trackers(self, ttl_minutes: int) -> dict:
        """Limpia trackers muertos vía RPC remoto"""
        try:
            resp = await self.dispatch(
                "Maintenance:update:remove_dead_trackers",
                {"ttl_minutes": ttl_minutes},
                "remove_dead_trackers",
            )
            return resp.data if resp else {}
        except Exception as e:
            logger.error(f"Error in remote remove_dead_trackers: {e}")
            return {}
