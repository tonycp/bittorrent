from dependency_injector import containers, providers
from bit_lib.services import PingSweepDiscovery
from bit_lib.context import VectorClock

from src.models import ClusterState
from src.settings.services import ClusterSettings, ReplicationSettings
from . import tracker, cluster, replication, cleanup

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
Configuration = providers.Configuration
Factory = providers.Factory
Singleton = providers.Singleton
DependenciesContainer = providers.DependenciesContainer


class ServiceContainer(DeclarativeContainer):
    config = Configuration()
    dispatcher = DependenciesContainer()
    repos = DependenciesContainer()
    handlers = DependenciesContainer()
    # wiring_config = WiringConfiguration(
    #     modules=[tracker, cluster, replication, cleanup],
    #     auto_wire=True,
    # )

    discovery_service = Factory(
        PingSweepDiscovery,
        host=config.tracker.host,
        port=config.tracker.port,
        ttl=30,
    )

    # Crear ClusterState compartido
    cluster_state = Singleton(
        ClusterState,
        tracker_id=config.tracker_id,
        host=config.tracker.host,
        port=config.cluster.port,
        query_count=0,
        vector_clock=VectorClock(),
        is_coordinator=True,  # Se autoasigna al inicio
        coordinator_id=config.tracker.host,  # IP del coordinador inicial (es uno mismo)
        coordinator_tracker_id=config.tracker_id,  # tracker_id del coordinador
    )

    # ClusterService con ClusterState y ClusterSettings
    cluster_settings = Singleton(
        ClusterSettings,
        host=config.cluster.host,
        port=config.cluster.port,
        sync_interval=config.cluster.sync_interval,
        heartbeat_interval=config.cluster.heartbeat_interval,
        liveness_timeout=config.cluster.liveness_timeout,
        purge_timeout=config.cluster.purge_timeout,
        cleanup_interval=config.cluster.cleanup_interval,
        service_name=config.cluster.service_name,
        heartbeat_fail_threshold=config.cluster.heartbeat_fail_threshold,
        election_semaphore_size=config.cluster.election_semaphore_size,
        discovery_timeout=config.cluster.discovery_timeout,
        discovery_ping_subnet=config.cluster.discovery_ping_subnet,
        discovery_ping_max_workers=config.cluster.discovery_ping_max_workers,
        rpc_timeout=config.cluster.rpc_timeout,
        min_cluster_size=config.cluster.min_cluster_size,
    )

    replication_settings = Singleton(
        ReplicationSettings,
        interval=config.replication.interval,
        heartbeat_interval=config.replication.heartbeat_interval,
        timeout=config.replication.timeout,
        max_retries=config.replication.max_retries,
    )

    cluster_service = Factory(
        cluster.ClusterService,
        host=config.tracker.host,
        port=config.cluster.port,
        cluster_state=cluster_state,
        settings=cluster_settings,
    )

    replication_service = Factory(
        replication.ReplicationService,
        host=config.tracker.host,
        port=config.tracker.port,
        tracker_id=config.tracker_id,
        cluster_service=cluster_service,
        settings=replication_settings,
        event_handler=handlers.event_hdl,
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
        cluster_service=cluster_service,
        replication_service=replication_service,
        cleanup_service=cleanup_service,
    )
