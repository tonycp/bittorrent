from bit_lib.context import save_config_to_ini
from src.const.c_env import DEFAULT_TRK_HOST

from src.containers import AppContainer

import asyncio
import socket


def main():
    container = AppContainer()

    if container.config.trk.host() == DEFAULT_TRK_HOST:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        container.config.trk.host.from_value(ip)
        save_config_to_ini(container.config())

    container.wire(modules=[__name__])
    container.gateways.create_db()

    service = container.services.tracker_service()

    asyncio.run(service.run())
