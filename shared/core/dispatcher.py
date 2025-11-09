from typing import Dict, List, Type
from shared.tools import BaseController


def get_endpoint(controller: BaseController):
    return controller.get_endpoint()


class Dispatcher:
    controllers: Dict[str, Type[BaseController]]
    actives: Dict[str, BaseController]

    def __init__(self, controllers: List[Type[BaseController]] = None):
        controllers = controllers or []
        self.controllers = dict(map(get_endpoint, controllers))
        self.actives: Dict[str, BaseController] = {}

    def register_controller(self, cls: Type[BaseController]):
        key = cls.get_endpoint()
        self.controllers[key] = cls

    def register_active(self, ctrl: BaseController):
        key = ctrl.get_endpoint()
        self.controllers[key] = ctrl.__class__
        self.actives[key] = ctrl

    def active_controller(self, route):
        cls = self.controllers.get(route)
        if not cls:
            raise ReferenceError("")
        ctrl = self.actives.get(route)
        if not ctrl:
            self.actives[route] = cls()
        return ctrl

    @staticmethod
    def process_controller(ctrl: BaseController, hdl_key: str, *args, **kwargs):
        return ctrl.process(hdl_key, *args, **kwargs)

    def dispatch(self, route, hdl_key, *args, **kwargs):
        ctrl = self.active_controller(route)
        return self.process_controller(ctrl, hdl_key, *args, **kwargs)
