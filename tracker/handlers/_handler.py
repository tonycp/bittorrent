from dependency_injector import containers, providers

from . import registry, session, tracker


class Handlers(containers.DeclarativeContainer):
    config = providers.Configuration()
    repo = providers.DependenciesContainer()
    wiring_config = containers.WiringConfiguration(
        modules=[registry, session, tracker],
        auto_wire=False,
    )

    tracker_hdl = providers.Factory(
        tracker.TrackerHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
    register_hdl = providers.Factory(
        registry.RegisterHandler,
        torrent_repo=repo.torrent_repo,
    )
    session_hdl = providers.Factory(
        session.SessionHandler,
        torrent_repo=repo.torrent_repo,
        peer_repo=repo.peer_repo,
    )
