from bit_lib.tools.controller import controller
from bit_lib.handlers.hander import BaseHandler
from bit_lib.handlers.crud import create, get
from bit_lib.errors import NotFoundError, ResourceConflictError
from bit_lib.models import DataResponse, RegisterSuccess

from src.repos import TorrentRepository, RepoContainer
from src.schemas.torrent import TorrentTable
from dependency_injector.wiring import Closing, Provide

from . import dtos

import logging


@controller("Register")
class RegisterHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[RepoContainer.torrent_repo]],
    ):
        super().__init__()
        self.torrent_repo = torrent_repo

    @get(dtos.FILE_INFO_DATASET)
    async def file_info(
        self,
        info_hash: str,
    ):
        logging.info(f"Getting file info for torrent with info hash: {info_hash}")
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise NotFoundError(info_hash, res_type="Torrent")

        return DataResponse(
            data={
                "info_hash": info_hash,
                "file_name": torrent.name,
                "file_size": torrent.size,
                "total_chunks": torrent.chunks,
            }
        )

    @create(dtos.CREATE_TORRENT_DATASET)
    async def create_torrent(
        self,
        info_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
    ):
        logging.info(f"Creating torrent with info hash: {info_hash}")

        torrent = await self.torrent_repo.get(info_hash)
        if torrent:
            raise ResourceConflictError(info_hash, res_type="Torrent")

        torrent = TorrentTable(
            info_hash=info_hash,
            name=file_name,
            size=file_size,
            chunks=total_chunks,
            peers=[],
        )

        await self.torrent_repo.add(torrent)
        return RegisterSuccess(
            message="Torrent registrado exitosamente",
            info_hash=info_hash,
        )
