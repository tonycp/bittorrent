from dependency_injector.wiring import Provide, Closing, inject
from tracker.containers import Server as ServerContainer
from tracker.settings.config import Configuration
from tracker.const.c_env import DEFAULT_TRK_HOST
from tracker import TrackerService
from tracker import handlers
from typing import Awaitable

import asyncio
import socket


def update_config(config: Configuration):
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    config.tracker.host = ip

    with open("config.json", "w+") as file:
        file.write(config.model_dump_json(indent=4))


def check_config(container: ServerContainer):
    config: Configuration = container.config.get_pydantic_settings()[0]
    if config.tracker.host == DEFAULT_TRK_HOST:
        update_config(config)
        container.config.from_pydantic(config)


@inject
async def run_tracker(
    host: str = Provide[ServerContainer.config.tracker.host],
    port: int = Provide[ServerContainer.config.tracker.port],
):
    service = TrackerService(host, port)
    await service.run()


@inject
async def main(
    create_db: Awaitable = Closing[Provide[ServerContainer.gateways.create_db]],
    container: ServerContainer = Provide[ServerContainer],
):
    await container.init_resources()
    await create_db()
    await run_tracker()


if __name__ == "__main__":
    container = ServerContainer()
    check_config(container)

    modules = [__name__, handlers]
    container.handlers.wire(modules=modules)
    container.gateways.wire(modules=modules)
    container.repositories.wire(modules=modules)
    container.wire(modules=modules)

    asyncio.run(main())
