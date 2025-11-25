from dependency_injector import containers, providers
from shared.context import dispatcher

# from tracker.handlers import RegisterHandler, SessionHandler, TrackerHandler


class Dispatchers(containers.DeclarativeContainer):
    config = providers.Configuration()
    handlers = providers.DependenciesContainer()

    tracker = providers.Factory(
        dispatcher.Dispatcher,
        controllers=[
            handlers.tracker_hdl,
            handlers.register_hdl,
            handlers.session_hdl,
        ],
    )
