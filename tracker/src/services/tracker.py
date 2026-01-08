from bit_lib.context import Dispatcher
from bit_lib.services import DispatcherService


class TrackerService(DispatcherService):
    """Tracker node service exposing RPC handlers via Dispatcher."""

    def __init__(
        self,
        host: str,
        port: int,
        dispatcher: Dispatcher,
        discovery_service=None,
        replication_service=None,
        cleanup_service=None,
    ):
        super().__init__(host, port, dispatcher)
        self.discovery_service = discovery_service
        self.replication_service = replication_service
        self.cleanup_service = cleanup_service

    async def run(self):
        """Start tracker service and background loops"""
        # Iniciar descubrimiento dinámico primero (para que trackers se registren)
        if self.discovery_service:
            await self.discovery_service.start()
        
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
        # Detener descubrimiento dinámico
        if self.discovery_service:
            await self.discovery_service.stop()
        
        # Detener loops de replicación
        if self.replication_service:
            await self.replication_service.stop_replication_loops()
        
        # Detener loop de limpieza
        if self.cleanup_service:
            await self.cleanup_service.stop_cleanup_loop()
        
        # Detener servidor principal
        await super().stop()

