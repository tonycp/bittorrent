from dependency_injector import containers, providers

from . import (
    bit,
    registry,
    session,
    tracker,
    maintenance,
    event,
    replication,
)

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
DependenciesContainer = providers.DependenciesContainer
Configuration = providers.Configuration
Factory = providers.Factory
Singleton = providers.Singleton


class HandlerContainer(DeclarativeContainer):
    config = Configuration()
    repo = DependenciesContainer()
    # wiring_config = WiringConfiguration(
    #     modules=[registry, session, bit, tracker, maintenance, event, replication],
    #     auto_wire=True,
    # )

    bit_hdl = Singleton(
        bit.BitHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
    tracker_hdl = Singleton(
        tracker.TrackerHandler,
        tracker_repo=repo.tracker_repo,
    )
    maintenance_hdl = Singleton(
        maintenance.MaintenanceHandler,
        peer_repo=repo.peer_repo,
        torrent_repo=repo.torrent_repo,
        event_repo=repo.event_log_repo,
    )
    register_hdl = Singleton(
        registry.RegisterHandler,
        torrent_repo=repo.torrent_repo,
    )
    session_hdl = Singleton(
        session.SessionHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
    event_hdl = Singleton(
        event.EventHandler,
        event_repo=repo.event_log_repo,
    )
    replication_hdl = Singleton(
        replication.ReplicationHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
        event_repo=repo.event_log_repo,
    )
