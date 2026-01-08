from typing import Dict, Iterable, TypeAlias

from bit_lib.services import UniqueService, ClientService
from bit_lib.proto import BlockCollector, BlockCollectorCache
from bit_lib.models import (
    decode_request,
    process_header,
    EventSuccess,
    MetaData,
    Request,
    Data,
)

from src.handlers import HandlerContainer, ReplicationHandler, EventHandler
from src.models.event import EventLog

RepHandler: TypeAlias = ReplicationHandler


class ReplicationService(UniqueService, ClientService):
    def __init__(self, host, port):
        super().__init__(host, port, EventHandler.endpoint)

        # self._blocks_cache: Dict[str, BlockCollectorCache] = {}

    # def get_block(self, meta: MetaData) -> BlockCollector:
    #     if meta.hash not in self._blocks_cache:
    #         block = BlockCollector(meta.hash, meta.total)
    #         cache_item = BlockCollectorCache(block=block, task=None, timestamp=0)
    #         self._blocks_cache.setdefault(meta.hash, cache_item)

    #     return self._blocks_cache[meta.hash]

    async def send_event(self, host: str, port: int, event: EventLog) -> None:
        req = Request(
            controller=self.service_id,
            command="update",
            func=event.operation,
            data=event.model_dump(),
        )
        await self.request(host, port, req, timeout=3.0)

    async def send_events(self, host: str, port: int, events: Iterable) -> None:
        for ev in events:
            await self.send_event(host, port, ev)

    async def _dispatch_request(
        self,
        hdl_key: str,
        data: Data,
        msg_id: str,
    ):
        event_hdl = HandlerContainer.event_hdl()
        response = await event_hdl._exec_handler(hdl_key, data)

        if isinstance(response, EventSuccess):
            header, data = decode_request(response.request)
            _, hdl_key = process_header(header)

            handler = HandlerContainer.replication_hdl()
            return await handler.process(hdl_key, data, msg_id)

    # async def _handle_binary(self, protocol, meta, data):
    #     block = self.get_block(meta)
    #     added = await block.add_block(meta.index, data)
