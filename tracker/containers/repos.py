from tracker.repos import PeerRepository, TorrentRepository


from dependency_injector import containers, providers


class Repositories(containers.DeclarativeContainer):
    config = providers.Configuration()
    session = providers.Resource()

    peer_repo = providers.Factory(
        PeerRepository,
        session=session,
    )

    torrent_repo = providers.Factory(
        TorrentRepository,
        session=session,
    )
