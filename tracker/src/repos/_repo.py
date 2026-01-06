from dependency_injector import containers, providers

from . import peer, torrent

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
DependenciesContainer = providers.DependenciesContainer
Configuration = providers.Configuration
Factory = providers.Factory


class RepoContainer(DeclarativeContainer):
    config = Configuration()
    gateways = DependenciesContainer()
    wiring_config = WiringConfiguration(
        modules=[peer, torrent],
        auto_wire=True,
    )

    peer_repo = Factory(
        peer.PeerRepository,
        session=gateways.session,
    )

    torrent_repo = Factory(
        torrent.TorrentRepository,
        session=gateways.session,
    )
