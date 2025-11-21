from dependency_injector.containers import DeclarativeContainer
from dependency_injector import providers

# import logging.config


class BaseContainer(DeclarativeContainer):
    config = providers.Configuration()

    # logging = providers.Resource(
    #     logging.config.dictConfig,
    #     config=config.logging,
    # )
