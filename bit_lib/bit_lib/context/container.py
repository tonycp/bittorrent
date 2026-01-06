from dependency_injector import providers, containers

import logging.config

DeclarativeContainer = containers.DeclarativeContainer
Configuration = providers.Configuration
Resource = providers.Resource


class BaseContainer(DeclarativeContainer):
    config = Configuration()

    logging = Resource(
        logging.config.dictConfig,
        config=config.logging,
    )
