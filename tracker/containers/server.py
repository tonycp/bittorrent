from shared.context.container import BaseContainer
from tracker.containers.dispatcher import Dispatchers
from tracker.containers.gateways import Gateways
from tracker.containers.handler import Handlers
from tracker.containers.repos import Repositories
from tracker.settings import get_settings

from dependency_injector import containers, providers


class Server(containers.DeclarativeContainer):
    config = providers.Configuration(default=get_settings(), ini_files=["./config.ini"])

    base = providers.Container(
        BaseContainer,
        config=config.base,
    )

    gateways = providers.Container(
        Gateways,
        config=config.database,
    )

    repositories = providers.Container(
        Repositories,
        config=config.repositories,
        session=gateways.session,
    )

    handlers = providers.Container(
        Handlers,
        config=config.handlers,
        repo=repositories,
    )

    dispatchers = providers.Container(
        Dispatchers,
        config=config.dispatchers,
        handlers=handlers,
    )
