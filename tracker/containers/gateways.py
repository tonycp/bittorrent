from dependency_injector import containers, providers

from tracker import database


class Gateways(containers.DeclarativeContainer):
    config = providers.Configuration()

    tracker_db = providers.Singleton(database.Database, db_url=config.url)
    create_db = providers.Singleton(tracker_db.provided.create_database_async.call())
    session = providers.Resource(tracker_db.provided.async_session.call())
