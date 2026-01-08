from dependency_injector import containers, providers
from bit_lib import Dispatcher

DeclarativeContainer = containers.DeclarativeContainer
Container = providers.DependenciesContainer
Configuration = providers.Configuration
Factory = providers.Factory


class DispatcherContainer(DeclarativeContainer):
    config = Configuration()
    handlers = Container()

    tracker = Factory(
        Dispatcher,
        controllers=[
            handlers.tracker_hdl,
            handlers.register_hdl,
            handlers.session_hdl,
            handlers.event_hdl,
            handlers.replication_hdl,
        ],
    )
