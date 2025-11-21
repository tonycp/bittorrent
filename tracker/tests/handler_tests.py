# async def exec_test(
#     service: TrackerService,
#     route: str,
#     method: str,
#     command: str,
#     data: Dict[str, Any],
# ):
#     names = list(data.keys())
#     id = ", ".join(f"{name}:?" for name in names)
#     hdl_key = get_index_sub(command, method, id)
#     result = await service._dispatch_message(route, hdl_key, data)
#     print(result)


# async def test_1(service: TrackerService):
#     route = handlers.RegisterHandler.endpoint
#     method = handlers.RegisterHandler.create_torrent.__name__
#     command = handlers.RegisterHandler.create_torrent.command
#     data = {
#         "info_hash": info_hash,
#         "file_name": peer_id,
#         "file_size": 600,
#         "total_chunks": 10,
#     }
#     await exec_test(service, route, method, command, data)


# async def test_2(service: TrackerService):
#     route = handlers.TrackerHandler.endpoint
#     method = handlers.TrackerHandler.announce.__name__
#     command = handlers.TrackerHandler.announce.command
#     data = {
#         "info_hash": info_hash,
#         "peer_id": peer_id,
#         "ip": "0.0.0.0",
#         "port": 5000,
#         "left": 0,
#         "event": "block",
#     }
#     await exec_test(service, route, method, command, data)
