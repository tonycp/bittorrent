from dependency_injector import containers, providers

from . import tracker


class Services(containers.DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration(
        modules=[tracker],
        auto_wire=False,
    )

    tracker_service = providers.Factory(
        tracker.TrackerService,
        host=config.tracker.host,
        port=config.tracker.port,
    )
