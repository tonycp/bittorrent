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


class HandlerContainer(DeclarativeContainer):
    config = Configuration()
    repo = DependenciesContainer()
    # wiring_config = WiringConfiguration(
    #     modules=[registry, session, bit, tracker, maintenance, event, replication],
    #     auto_wire=True,
    # )

    bit_hdl = Factory(
        bit.BitHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
    tracker_hdl = Factory(
        tracker.TrackerHandler,
        tracker_repo=repo.tracker_repo,
    )
    maintenance_hdl = Factory(
        maintenance.MaintenanceHandler,
        peer_repo=repo.peer_repo,
        torrent_repo=repo.torrent_repo,
        event_repo=repo.event_log_repo,
    )
    register_hdl = Factory(
        registry.RegisterHandler,
        torrent_repo=repo.torrent_repo,
    )
    session_hdl = Factory(
        session.SessionHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
    event_hdl = Factory(
        event.EventHandler,
        event_repo=repo.event_repo,
    )
    replication_hdl = Factory(
        replication.ReplicationHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
        event_repo=repo.event_log_repo,
    )
