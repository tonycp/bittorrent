from dependency_injector import containers, providers

from . import database


class SessionResource(providers.Resource):
    pass


class Gateways(containers.DeclarativeContainer):
    config = providers.Configuration()
    wiring_config = containers.WiringConfiguration(
        modules=[database],
        auto_wire=False,
    )

    tracker_db = providers.Singleton(
        database.Database,
        db_url=config.url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_recycle=config.pool_recycle,
    )
    create_db = providers.Resource(tracker_db.provided.create_database_async)
    session_factory = providers.Resource(tracker_db.provided._session_factory)
    session = providers.Resource(tracker_db.provided.async_session.call())
