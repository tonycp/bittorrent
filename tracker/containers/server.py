from prueba._services import Services
from shared.context.container import BaseContainer
from tracker.containers.dispatcher import Dispatchers
from tracker.database._gateway import Gateways
from tracker.handlers._handler import Handlers
from tracker.repos._repo import Repositories
from tracker.settings import Configuration

from dependency_injector import containers, providers


class Server(containers.DeclarativeContainer):
    config = providers.Configuration(pydantic_settings=[Configuration()])

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
        gateways=gateways,
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

    services = providers.Container(
        Services,
        config=config.services,
    )
