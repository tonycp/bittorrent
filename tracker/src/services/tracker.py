from bit_lib.context import Dispatcher
from bit_lib.services import DispatcherService
from bit_lib.models import Response, Error

from .cleanup import CleanupService
from .cluster import ClusterService
from .replication import ReplicationService

import logging

logger = logging.getLogger(__name__)


class TrackerService(DispatcherService):
    """Tracker node service exposing RPC handlers via Dispatcher."""

    def __init__(
        self,
        host: str,
        port: int,
        dispatcher: Dispatcher,
        cluster_service: ClusterService = None,
        replication_service: ReplicationService = None,
        cleanup_service: CleanupService = None,
    ):
        super().__init__(host, port, dispatcher)
        self.cluster_service = cluster_service
        self.replication_service = replication_service
        self.cleanup_service = cleanup_service

    # ==================== MessageService Abstract Methods ====================

    async def _handle_binary(self, protocol, meta, data: bytes):
        """Handle binary data transfer"""
        logger.warning("Binary data received but not implemented yet in TrackerService")

    async def _handle_response(self, protocol, response: Response):
        """Handle response messages"""
        logger.debug(f"Response received: {response.reply_to}")

    async def _handle_error(self, protocol, error: Error):
        """Handle error messages"""
        logger.error(f"Error received: {error.data}")

    async def _on_connect(self, protocol):
        """Called when a new connection is established"""
        logger.debug("New connection established to tracker")

    async def _on_disconnect(self, protocol, exc):
        """Called when a connection is closed"""
        if exc:
            logger.debug(f"Connection closed with error: {exc}")
        else:
            logger.debug("Connection closed cleanly")

    # ==================== Lifecycle ====================

    async def run(self):
        """Start tracker service and background loops"""

        # Iniciar sincronización de cluster (membresía + elección)
        if self.cluster_service:
            await self.cluster_service.start_cluster_sync()

        # Iniciar loops de replicación si existe el servicio
        if self.replication_service:
            await self.replication_service.start_replication_loops()

        # Iniciar loop de limpieza si existe el servicio
        if self.cleanup_service:
            await self.cleanup_service.start_cleanup_loop()

        # Iniciar servidor principal
        await super().run()

    async def stop(self):
        """Stop tracker service and background loops"""

        # Detener sincronización de cluster
        if self.cluster_service:
            await self.cluster_service.stop_cluster_sync()

        # Detener loops de replicación
        if self.replication_service:
            await self.replication_service.stop_replication_loops()

        # Detener loop de limpieza
        if self.cleanup_service:
            await self.cleanup_service.stop_cleanup_loop()

        # Detener servidor principal
        await super().stop()
