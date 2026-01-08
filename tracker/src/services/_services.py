from dependency_injector import containers, providers
from bit_lib.services import PingSweepDiscovery

from . import tracker, replication, cleanup

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
Configuration = providers.Configuration
Factory = providers.Factory
DependenciesContainer = providers.DependenciesContainer


class ServiceContainer(DeclarativeContainer):
    config = Configuration()
    dispatcher = DependenciesContainer()
    repos = DependenciesContainer()
    handlers = DependenciesContainer()
    wiring_config = WiringConfiguration(
        modules=[tracker, replication, cleanup],
        auto_wire=True,
    )

    discovery_service = Factory(
        PingSweepDiscovery,
        host=config.tracker.host,
        port=config.tracker.port,
        ttl=30,
    )

    replication_service = Factory(
        replication.ReplicationService,
        host=config.tracker.host,
        port=config.tracker.port,
        tracker_id=config.tracker_id,
        neighbors=config.neighbors,
        replication_interval=config.replication.interval,
        heartbeat_interval=config.replication.heartbeat_interval,
        timeout=config.replication.timeout,
        max_retries=config.replication.max_retries,
        discovery_service=discovery_service,
    )
    
    cleanup_service = Factory(
        cleanup.CleanupService,
        host=config.tracker.host,
        port=config.tracker.port,
        maintenance_handler=handlers.maintenance_hdl,
        interval=config.cleanup.interval,
        peer_ttl_minutes=config.cleanup.peer_ttl_minutes,
        event_retention_minutes=config.cleanup.event_retention_minutes,
        tracker_ttl_minutes=getattr(config.cleanup, "tracker_ttl_minutes", 60),
    )

    tracker_service = Factory(
        tracker.TrackerService,
        host=config.tracker.host,
        port=config.tracker.port,
        dispatcher=dispatcher.tracker,
        discovery_service=discovery_service,
        replication_service=replication_service,
        cleanup_service=cleanup_service,
    )
