from bit_lib.tools.controller import controller
from bit_lib.handlers.hander import BaseHandler
from bit_lib.handlers.crud import create, get
from bit_lib.errors import NotFoundError, ResourceConflictError
from bit_lib.models import DataResponse, RegisterSuccess

from src.repos import TorrentRepository, RepoContainer
from src.schemas.torrent import TorrentTable
from dependency_injector.wiring import Closing, Provide

from . import dtos

import os
import logging


@controller("Register")
class RegisterHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[RepoContainer.torrent_repo]],
    ):
        super().__init__()
        self.torrent_repo = torrent_repo
        self.tracker_id = os.environ.get("TRACKER_ID", "tracker-1")
        self.request_handler = None  # Se asigna desde TrackerService

    @get(dtos.FILE_INFO_DATASET)
    async def file_info(
        self,
        info_hash: str,
    ):
        logging.info(f"Consultando metadatos del torrent: {info_hash}")

        # Intentamos obtener el torrent por su identificador único (info_hash)
        torrent = await self.torrent_repo.get(info_hash)

        if not torrent:
            raise NotFoundError(info_hash, res_type="Torrent")

        # En BitTorrent, los 'chunks' se conocen técnicamente como 'pieces'
        return DataResponse(
            data={
                "info_hash": info_hash,
                "name": torrent.name,
                "size": torrent.size,
                "total_pieces": torrent.chunks,
            }
        )

    @create(dtos.CREATE_TORRENT_DATASET)
    async def create_torrent(
        self,
        info_hash: str,
        file_name: str,
        file_size: int,
        total_chunks: int,
        piece_length: int,  # <--- ¡Crucial para los clientes!
    ):
        logging.info(f"Registrando nuevo torrent en el tracker: {info_hash}")

        existing_torrent = await self.torrent_repo.get(info_hash)
        if existing_torrent:
            raise ResourceConflictError(info_hash, res_type="Torrent")

        # Nota: No inicializamos 'peers' como lista vacía aquí si es una relación
        # Many-to-Many; la tabla intermedia se encargará de eso.
        torrent = TorrentTable(
            info_hash=info_hash,
            name=file_name,
            size=file_size,
            chunks=total_chunks,
            piece_length=piece_length,
        )

        await self.torrent_repo.add(torrent)

        # Generar evento para replicación
        logging.info(f"[{self.tracker_id}] Intentando crear evento para torrent_created")
        logging.info(f"[{self.tracker_id}] request_handler is: {self.request_handler}")
        await self._create_event(
            operation="torrent_created",
            data={
                "info_hash": info_hash,
                "file_name": file_name,
                "file_size": file_size,
                "total_chunks": total_chunks,
                "piece_length": piece_length,
            }
        )

        logging.info(
            f"Torrent '{file_name}' ({file_size} bytes) registrado correctamente."
        )

        return RegisterSuccess(
            message="Torrent registrado exitosamente",
            info_hash=info_hash,
        )

    async def _create_event(self, operation: str, data: dict):
        """Helper para crear eventos que se replicarán entre trackers via callback"""
        from bit_lib.models import Request
        
        logging.info(f"[{self.tracker_id}] _create_event called: operation={operation}")
        
        if not self.request_handler:
            logging.warning(f"[{self.tracker_id}] No request_handler available, skipping event creation")
            return
        
        logging.info(f"[{self.tracker_id}] request_handler exists, creating request")
        
        try:
            # Crear request para EventHandler
            req = Request(
                controller="Event",
                command="create",
                func="create_event",
                args={
                    "tracker_id": self.tracker_id,
                    "operation": operation,
                    "data": data,
                },
            )
            logging.info(f"[{self.tracker_id}] Calling request_handler")
            # Llamar directamente al handler del servidor principal
            result = await self.request_handler(req)
            logging.info(f"[{self.tracker_id}] Evento creado: {operation}, result={result}")
        except Exception as e:
            import traceback
            logging.error(f"[{self.tracker_id}] Error creando evento: {e}")
            logging.error(f"[{self.tracker_id}] Traceback: {traceback.format_exc()}")
