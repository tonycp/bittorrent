from dependency_injector import providers

from bit_lib.tools import BaseController

from typing import Dict, List

Factory = providers.Factory
Provider = providers.Provider


def get_endpoint(controller: Factory[BaseController]) -> str:
    provides = controller.provides()
    assert provides
    return provides.endpoint


def gen_pair(controller: Factory[BaseController]):
    return get_endpoint(controller), controller


class Dispatcher:
    controllers: Dict[str, Factory[BaseController]]

    def __init__(
        self,
        controllers: List[Factory[BaseController]] = None,
    ):
        controllers = controllers or []
        self.controllers = dict(map(gen_pair, controllers))
        self.actives: Dict[str, Factory[BaseController]] = {}

    def register_controller(self, factory: Factory[BaseController]):
        key = get_endpoint(factory)
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
