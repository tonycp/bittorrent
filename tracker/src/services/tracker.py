from dependency_injector.wiring import Provide, Closing

from bit_lib.models.typing import Data
from bit_lib.context import Dispatcher
from bit_lib.core import HandlerService

from src.containers import AppContainer


class TrackerService(HandlerService):
    async def _handle_binary(self, protocol, meta, data):
        return await super()._handle_binary(protocol, meta, data)

    async def _on_connect(self, protocol):
        return await super()._on_connect(protocol)

    async def _on_disconnect(self, protocol, exc):
        return await super()._on_disconnect(protocol, exc)

    async def _dispatch_message(
        self,
        route: str,
        hdl_key: str,
        data: Data,
        msg_id: str = None,
        dispatcher: Dispatcher = Closing[Provide[AppContainer.dispatchers.tracker]],
    ):
        return await dispatcher.dispatch(route, hdl_key, data, msg_id)
