from dependency_injector import containers, providers

from . import tracker

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
Configuration = providers.Configuration
Factory = providers.Factory


class ServiceContainer(DeclarativeContainer):
    config = Configuration()
    wiring_config = WiringConfiguration(
        modules=[tracker],
        auto_wire=True,
    )

    tracker_service = Factory(
        tracker.TrackerService,
        host=config.tracker.host,
        port=config.tracker.port,
    )
