from shared.context import dispatcher


from dependency_injector import containers, providers


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