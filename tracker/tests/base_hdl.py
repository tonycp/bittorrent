from shared.context.dispatcher import Dispatcher
from shared.tools.subscribe import get_index_sub
from shared.models.typing import Data

from dependency_injector.wiring import Provide, Closing
from tracker.containers import Server
from tracker import handlers


async def exec_test(
    route: str,
    method: str,
    command: str,
    data: Data,
    dispatcher: Dispatcher = Closing[Provide[Server.dispatchers.tracker]],
):
    names = list(data.keys())
    id = ", ".join(f"{name}:?" for name in names)
    hdl_key = get_index_sub(command, method, id)
    return await dispatcher.dispatch(route, hdl_key, data)


async def announce(
    info_hash,
    peer_id,
    ip,
    port,
    left,
    event,
):
    route = handlers.TrackerHandler.endpoint
    method = handlers.TrackerHandler.announce.__name__
    command = handlers.TrackerHandler.announce.command
    data = {
        "info_hash": info_hash,
        "peer_id": peer_id,
        "ip": ip,
        "port": port,
        "left": left,
        "event": event,
    }
    await exec_test(route, method, command, data)


async def handshake(peer_id, protocol_version):
    route = handlers.SessionHandler.endpoint
    method = handlers.SessionHandler.handshake.__name__
    command = handlers.SessionHandler.handshake.command
    data = {"peer_id": peer_id, "protocol_version": protocol_version}

    await exec_test(route, method, command, data)


async def disconnect(peer_id, info_hash):
    route = handlers.SessionHandler.endpoint
    method = handlers.SessionHandler.disconnect.__name__
    command = handlers.SessionHandler.disconnect.command
    data = {"peer_id": peer_id, "info_hash": info_hash}

    await exec_test(route, method, command, data)


async def keepalive(peer_id):
    route = handlers.SessionHandler.endpoint
    method = handlers.SessionHandler.keepalive.__name__
    command = handlers.SessionHandler.keepalive.command
    data = {"peer_id": peer_id}

    await exec_test(route, method, command, data)


async def peer_list(info_hash):
    route = handlers.TrackerHandler.endpoint
    method = handlers.TrackerHandler.peer_list.__name__
    command = handlers.TrackerHandler.peer_list.command
    data = {"info_hash": info_hash}

    await exec_test(route, method, command, data)


async def file_info(info_hash):
    route = handlers.RegisterHandler.endpoint
    method = handlers.RegisterHandler.file_info.__name__
    command = handlers.RegisterHandler.file_info.command
    data = {"info_hash": info_hash}

    await exec_test(route, method, command, data)


async def create_torrent(
    info_hash,
    file_name,
    file_size,
    total_chunks,
):
    route = handlers.RegisterHandler.endpoint
    method = handlers.RegisterHandler.create_torrent.__name__
    command = handlers.RegisterHandler.create_torrent.command
    data = {
        "info_hash": info_hash,
        "file_name": file_name,
        "file_size": file_size,
        "total_chunks": total_chunks,
    }
    await exec_test(route, method, command, data)
