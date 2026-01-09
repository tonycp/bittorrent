from dependency_injector import containers, providers

from . import database

DeclarativeContainer = containers.DeclarativeContainer
WiringConfiguration = containers.WiringConfiguration
Configuration = providers.Configuration
Singleton = providers.Singleton
Resource = providers.Resource


class SessionResource(Resource):
    pass


class GatewayContainer(DeclarativeContainer):
    config = Configuration()
    # wiring_config = WiringConfiguration(
    #     modules=[database],
    #     auto_wire=True,
    # )

    tracker_db = Singleton(
        database.Database,
        db_url=config.url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_recycle=config.pool_recycle,
    )
    create_db = Resource(tracker_db.provided.create_database_async)
    session_factory = Resource(tracker_db.provided._session_factory)
    session = Resource(tracker_db.provided.async_session.call())
