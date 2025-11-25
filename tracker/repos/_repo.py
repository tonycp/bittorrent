from dependency_injector import containers, providers

from . import peer_repo, torrent_repo


class Repositories(containers.DeclarativeContainer):
    config = providers.Configuration()
    gateways = providers.DependenciesContainer()
    # wiring_config = containers.WiringConfiguration(
    #     modules=[peer_repo, torrent_repo],
    #     auto_wire=False,
    # )

    peer_repo = providers.Factory(
        peer_repo.PeerRepository,
        session=gateways.session,
    )

    torrent_repo = providers.Factory(
        torrent_repo.TorrentRepository,
        session=gateways.session,
    )
