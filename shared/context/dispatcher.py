from typing import Dict, List
from shared.tools import BaseController
from dependency_injector.providers import Factory, Provider


def get_endpoint(controller: Factory[BaseController]):
    return controller.provides.endpoint, controller


class Dispatcher:
    controllers: Dict[str, Factory[BaseController]]

    def __init__(
        self,
        controllers: List[Factory[BaseController]] = None,
    ):
        controllers = controllers or []
        self.controllers = dict(map(get_endpoint, controllers))
        self.actives: Dict[str, Factory[BaseController]] = {}

    def register_controller(self, factory: Factory[BaseController]):
        key = factory.provides.endpoint
        self.controllers[key] = factory

    async def activate_controller(self, route: str) -> BaseController:
        provider = self.controllers[route]
        if not Provider.is_async_mode_enabled(provider):
            Provider.enable_async_mode(provider)
        return await provider()

    @staticmethod
    async def process_controller(ctrl: BaseController, hdl_key: str, *args, **kwargs):
        return await ctrl.process(hdl_key, *args, **kwargs)

    async def dispatch(self, route, hdl_key, *args, **kwargs):
        ctrl = await self.activate_controller(route)
        return await self.process_controller(ctrl, hdl_key, *args, **kwargs)
