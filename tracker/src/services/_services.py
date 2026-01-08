from dependency_injector import containers, providers

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
    wiring_config = WiringConfiguration(
        modules=[tracker, replication, cleanup],
        auto_wire=True,
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
    )
    
    cleanup_service = Factory(
        cleanup.CleanupService,
        peer_repo=repos.peer_repo,
        torrent_repo=repos.torrent_repo,
        event_repo=repos.event_log_repo,
        interval=config.cleanup.interval,
        peer_ttl_minutes=config.cleanup.peer_ttl_minutes,
        event_retention_minutes=config.cleanup.event_retention_minutes,
    )

    tracker_service = Factory(
        tracker.TrackerService,
        host=config.tracker.host,
        port=config.tracker.port,
        dispatcher=dispatcher.tracker,
        replication_service=replication_service,
        cleanup_service=cleanup_service,
    )
