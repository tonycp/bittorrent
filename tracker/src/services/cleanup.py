import asyncio
import logging

from bit_lib.services import UniqueService, ClientService
from bit_lib.models import Data
from bit_lib.handlers import BaseMaintenanceHandler

logger = logging.getLogger(__name__)


class CleanupService(UniqueService, ClientService):
    """Servicio de limpieza periódica con puerto propio (RPC escalable)"""

    def __init__(
        self,
        host: str,
        port: int,
        maintenance_handler: BaseMaintenanceHandler,
        interval: int = 300,
        peer_ttl_minutes: int = 30,
        event_retention_minutes: int = 10,
        tracker_ttl_minutes: int = 60,
    ):
        super().__init__(host, port, "Cleanup")
        self.maintenance_handler = maintenance_handler
        self.interval = interval
        self.peer_ttl_minutes = peer_ttl_minutes
        self.event_retention_minutes = event_retention_minutes
        self.tracker_ttl_minutes = tracker_ttl_minutes

        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def _dispatch_request(self, hdl_key: str, data: Data, msg_id: str):
        """Redirige requests externos al MaintenanceHandler (para RPC entrante)"""
        return await self.maintenance_handler.dispatch(hdl_key, data, msg_id)

    async def start_cleanup_loop(self):
        """Inicia el loop periódico de limpieza"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup loop started")

    async def stop_cleanup_loop(self):
        """Detiene el loop de limpieza"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Cleanup loop stopped")

    async def _cleanup_loop(self):
        """Loop principal que ejecuta limpieza periódicamente"""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._perform_cleanup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _perform_cleanup(self):
        """Orquesta todas las tareas de limpieza delegando a métodos específicos"""
        try:
            await self._cleanup_peers()
            await self._cleanup_torrents()
            await self._cleanup_events()
            await self._cleanup_trackers()
        except Exception as e:
            logger.error(f"Error performing cleanup orchestration: {e}")

    async def _cleanup_peers(self):
        """Limpia peers inactivos vía MaintenanceClient"""
        try:
            result = await self.maintenance_client.cleanup_peers(self.peer_ttl_minutes)
            if result.get("removed_peers", 0) > 0:
                logger.info(f"Removed {result['removed_peers']} inactive peers")
        except Exception as e:
            logger.warning(f"Failed to cleanup peers: {e}")

    async def _cleanup_torrents(self):
        """Limpia torrents huérfanos vía MaintenanceClient"""
        try:
            result = await self.maintenance_client.cleanup_torrents()
            if result.get("removed_torrents", 0) > 0:
                logger.info(f"Removed {result['removed_torrents']} orphaned torrents")
        except Exception as e:
            logger.warning(f"Failed to cleanup torrents: {e}")

    async def _cleanup_events(self):
        """Limpia eventos antiguos vía MaintenanceClient"""
        try:
            result = await self.maintenance_client.cleanup_events(
                self.event_retention_minutes
            )
            if result.get("removed_events", 0) > 0:
                logger.info(f"Purged {result['removed_events']} old events")
        except Exception as e:
            logger.warning(f"Failed to cleanup events: {e}")

    async def _cleanup_peers(self):
        """Limpia peers inactivos vía MaintenanceHandler"""
        try:
            result = await self.maintenance_handler.cleanup_peers(self.peer_ttl_minutes)
            if result.get("removed_peers", 0) > 0:
                logger.info(f"Removed {result['removed_peers']} inactive peers")
        except Exception as e:
            logger.warning(f"Failed to cleanup peers: {e}")

    async def _cleanup_torrents(self):
        """Limpia torrents huérfanos vía MaintenanceHandler"""
        try:
            result = await self.maintenance_handler.cleanup_torrents()
            if result.get("removed_torrents", 0) > 0:
                logger.info(f"Removed {result['removed_torrents']} orphaned torrents")
        except Exception as e:
            logger.warning(f"Failed to cleanup torrents: {e}")

    async def _cleanup_events(self):
        """Limpia eventos antiguos vía MaintenanceHandler"""
        try:
            result = await self.maintenance_handler.cleanup_events(
                self.event_retention_minutes
            )
            if result.get("removed_events", 0) > 0:
                logger.info(f"Purged {result['removed_events']} old events")
        except Exception as e:
            logger.warning(f"Failed to cleanup events: {e}")

    async def _cleanup_trackers(self):
        """Limpia trackers muertos vía MaintenanceHandler"""
        try:
            result = await self.maintenance_handler.remove_dead_trackers(
                self.tracker_ttl_minutes
            )
            if result.get("removed_count", 0) > 0:
                logger.info(
                    f"Removed {result['removed_count']} dead trackers from registry"
                )
        except Exception as e:
            logger.warning(f"Failed to cleanup trackers: {e}")