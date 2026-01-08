from bit_lib import BaseContainer

from src.settings import AppSettings
from src.repos._repo import RepoContainer
from src.database._gateway import GatewayContainer
from src.handlers._handler import HandlerContainer
from src.services._services import ServiceContainer

from dependency_injector import containers, providers

from .dispatcher import DispatcherContainer

DeclarativeContainer = containers.DeclarativeContainer
Container = providers.Container


class AppContainer(DeclarativeContainer):
    config = providers.Configuration(pydantic_settings=[AppSettings()])

    base = Container(
        BaseContainer,
        config=config.base,
    )

    gateways = Container(
        GatewayContainer,
        config=config.database,
    )

    repositories = Container(
        RepoContainer,
        config=config.repositories,
        gateways=gateways,
    )

    handlers = Container(
        HandlerContainer,
        repo=repositories,
    )

    dispatchers = Container(
        DispatcherContainer,
        config=config.dispatchers,
        handlers=handlers,
    )

    services = Container(
        ServiceContainer,
        config=config.services,
        dispatcher=dispatchers,
        repos=repositories,
    )
