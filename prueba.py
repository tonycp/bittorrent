from shared.context import save_config_to_ini
from tracker.containers import Server as ServerContainer
from tracker.const.c_env import DEFAULT_TRK_HOST
from tracker import TrackerService

from uuid import uuid4
import asyncio

import socket


info_hash = uuid4().hex
peer_id = uuid4().hex


def main():
    container = ServerContainer()

    if container.config.trk.host() == DEFAULT_TRK_HOST:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        container.config.trk.host.from_value(ip)
        save_config_to_ini(container.config())

    container.wire(modules=[__name__])
    container.gateways.create_db()

    service = TrackerService(
        container.base.config.tracker.host(),
        container.base.config.tracker.port(),
    )

    asyncio.run(service.run())


if __name__ == "__main__":
    main()
