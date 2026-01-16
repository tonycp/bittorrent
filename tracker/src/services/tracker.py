from bit_lib.context import Dispatcher
from bit_lib.services import DispatcherService
from bit_lib.models import Response, Error, Request
from bit_lib.errors import BaseError

from .cleanup import CleanupService
from .cluster import ClusterService
from .replication import ReplicationService

import asyncio
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
        
        # Controllers que requieren cluster estable (operaciones de cliente)
        self._client_controllers = {"Bit", "Event", "Registry"}
        # Controllers internos que siempre pueden operar
        self._internal_controllers = {"Cluster", "Replication", "Maintenance"}

    # ==================== MessageService Abstract Methods ====================

    async def _process_request(self, request: Request):
        """
        Procesa requests verificando estabilidad del cluster para operaciones de cliente.
        
        - Controllers de cliente (Bit, Event, Registry): Requieren cluster estable
        - Controllers internos (Cluster, Replication, Maintenance): Siempre operan
        """
        controller = request.controller
        
        # Verificar si es una operación de cliente que requiere cluster estable
        if controller in self._client_controllers:
            if self.cluster_service and not await self.cluster_service.is_cluster_stable():
                logger.warning(
                    f"Rejecting {controller} request - cluster unstable "
                    f"(size={self.cluster_service.get_cluster_size()}, "
                    f"min={self.cluster_service.settings.min_cluster_size})"
                )
                raise BaseError(
                    status=503,
                    message="Cluster unstable - operation temporarily unavailable",
                    details={
                        "error_type": "ClusterUnstable",
                        "reason": "Waiting for cluster stabilization",
                        "cluster_size": self.cluster_service.get_cluster_size(),
                        "min_required": self.cluster_service.settings.min_cluster_size,
                    },
                )
        
        # Procesar normalmente (cluster estable o controller interno)
        return await super()._process_request(request)

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

        # Crear wrapper para llamadas internas sin protocolo
        async def internal_request_handler(request):
            from bit_lib.models import decode_request, process_header
            header, data = decode_request(request)
            route, hdl_key = process_header(header)
            args = data, request.msg_id
            return await self._dispatch_request(route, hdl_key, *args)

        # Pasar callback de internal_request_handler a los handlers que crean eventos
        logger.info(f"TrackerService: Configurando callbacks para {len(self.dispatcher.controllers)} controllers")
        for endpoint, controller_factory in self.dispatcher.controllers.items():
            # Obtener la instancia del controller desde el factory
            controller = await controller_factory()
            # Asignar callback
            controller.request_handler = internal_request_handler
            logger.info(f"TrackerService: Callback configurado en {endpoint} ({controller.__class__.__name__})")

        # Pasar callback de internal_request_handler a replication service para crear eventos
        if self.replication_service:
            self.replication_service.request_handler = internal_request_handler
            logger.info("TrackerService: Callback configurado en ReplicationService")

        # Iniciar sincronización de cluster (membresía + elección)
        if self.cluster_service:
            # Start cluster server listening for peer messages in parallel
            cluster_task = asyncio.create_task(self.cluster_service.run())
        else:
            cluster_task = None

        # Iniciar loops de replicación si existe el servicio
        if self.replication_service:
            await self.replication_service.start_replication_loops()

        # Iniciar loop de limpieza si existe el servicio
        if self.cleanup_service:
            await self.cleanup_service.start_cleanup_loop()

        try:
            # Iniciar servidor RPC principal; cluster server runs in parallel
            await super().run()
        finally:
            # Cancel cluster server if it was started
            if cluster_task:
                cluster_task.cancel()
                try:
                    await cluster_task
                except asyncio.CancelledError:
                    pass

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
