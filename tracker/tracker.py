from dependency_injector.wiring import Provide, Closing

from tracker.containers import Server as ServerContainer
from shared.models.typing import Data
from shared.context import Dispatcher
from shared.core import HandlerService


class TrackerService(HandlerService):
    async def _dispatch_message(self, route, hdl_key, data):
        return await self._dispatch(route, hdl_key, data)

    async def _handle_binary(self, protocol, meta, data):
        return await super()._handle_binary(protocol, meta, data)

    async def _on_connect(self, protocol):
        return await super()._on_connect(protocol)

    async def _on_disconnect(self, protocol, exc):
        return await super()._on_disconnect(protocol, exc)

    async def _dispatch(
        self,
        route: str,
        hdl_key: str,
        data: Data,
        dispatcher: Dispatcher = Closing[Provide[ServerContainer.dispatchers.tracker]],
    ):
        return await dispatcher.dispatch(route, hdl_key, data)
