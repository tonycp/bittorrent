from bit_lib.context import save_config_to_ini
from src.const.c_env import DEFAULT_TRK_HOST

from src.containers import AppContainer

import asyncio
import socket
import logging


# Configuración básica de logs para ver flujos en consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    container = AppContainer()

    cfg = container.config.services

    if cfg.tracker.host() == DEFAULT_TRK_HOST:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        cfg.tracker.host.from_value(ip)
        # TODO: save_config_to_ini fails with logging config ('%' interpolation)
        # save_config_to_ini(container.config())

    container.wire(modules=[__name__])

    # create_db es un Resource que retorna corutina, necesita asyncio
    asyncio.run(run_tracker(container))


async def run_tracker(container):
    """Función async para inicializar DB y arrancar el tracker"""
    container.gateways.create_db()

    # Obtener service (puede ser un Provider que devuelve Future/instancia)
    service_provider = container.services.tracker_service
    logger.info(f"Service provider type: {type(service_provider)}")

    service = await service_provider()

    await service.run()
