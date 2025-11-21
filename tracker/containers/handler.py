from tracker.handlers import RegisterHandler, SessionHandler, TrackerHandler


from dependency_injector import containers, providers


class Handlers(containers.DeclarativeContainer):
    config = providers.Configuration()
    repo = providers.DependenciesContainer()

    tracker_hdl = providers.Factory(
        TrackerHandler,
        peer_repo=repo.peer_repo,
        torrent_repo=repo.torrent_repo,
    )

    register_hdl = providers.Factory(
        RegisterHandler,
        torrent_repo=repo.torrent_repo,
    )

    session_hdl = providers.Factory(
        SessionHandler,
        peer_repo=repo.peer_repo,
        torrent_repo=repo.torrent_repo,
    )
