from shared.handlers.crud import create, get
from shared.handlers.hander import BaseHandler

from tracker.repos import TorrentRepository
from shared.tools.controller import controller
from tracker.schemas.torrent import TorrentTable

from . import dtos


@controller("Register")
class RegisterHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository,
    ):
        super().__init__()
        self.torrent_repo = torrent_repo

    @get(dtos.FILE_INFO_DATASET)
    async def file_info(
        self,
        info_hash: str,
    ):
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        return {
            "info_hash": info_hash,
            "file_name": torrent.name,
            "file_size": torrent.size,
            "total_chunks": torrent.chunks,
        }

    @create(dtos.CREATE_TORRENT_DATASET)
    async def create_torrent(
        self,
        info_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
    ):
        # Verifica si el torrent ya existe
        torrent = await self.torrent_repo.get(info_hash)
        if torrent:
            return {
                "status": "already_exists",
                "message": "El torrent ya está registrado",
                "info_hash": info_hash,
            }
        # Crea y almacena el nuevo torrent
        torrent = TorrentTable(
            info_hash=info_hash,
            name=file_name,
            size=file_size,
            chunks=total_chunks,
            peers=[],  # Inicialmente vacío
        )
        await self.torrent_repo.add(torrent)
        return {
            "status": "ok",
            "message": "Torrent creado exitosamente",
            "info_hash": info_hash,
        }
