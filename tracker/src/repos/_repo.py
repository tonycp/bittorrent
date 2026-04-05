from dependency_injector import containers, providers

from . import peer, torrent, event, tracker, replica_assignment

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
DependenciesContainer = providers.DependenciesContainer
Configuration = providers.Configuration
Factory = providers.Factory


class RepoContainer(DeclarativeContainer):
    config = Configuration()
    gateways = DependenciesContainer()
    # wiring_config = WiringConfiguration(
    #     modules=[peer, torrent],
    #     auto_wire=True,
    # )

    peer_repo = Factory(
        peer.PeerRepository,
        session=gateways.session,
    )

    torrent_repo = Factory(
        torrent.TorrentRepository,
        session=gateways.session,
    )

    event_log_repo = Factory(
        event.EventLogRepository,
        session=gateways.session,
    )

    tracker_repo = Factory(
        tracker.TrackerRepository,
        session=gateways.session,
    )

    replica_assignment_repo = Factory(
        replica_assignment.ReplicaAssignmentRepository,
        session=gateways.session,
    )
