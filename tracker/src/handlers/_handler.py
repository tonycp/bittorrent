from dependency_injector import containers, providers

from . import (
    registry,
    session,
    tracker,
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
    wiring_config = WiringConfiguration(
        modules=[registry, session, tracker, event, replication],
        auto_wire=True,
    )

    tracker_hdl = Factory(
        tracker.TrackerHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
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
