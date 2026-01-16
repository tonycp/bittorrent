from bit_lib.tools.controller import controller
from bit_lib.handlers.hander import BaseHandler
from bit_lib.handlers.crud import create, delete, update
from bit_lib.errors import NotFoundError
from bit_lib.models import HandshakeSuccess, DisconnectSuccess, KeepaliveSuccess, DataResponse

from src.repos import PeerRepository, TorrentRepository, RepoContainer
from src.schemas.torrent import PeerTable
from dependency_injector.wiring import Closing, Provide
from datetime import datetime, timezone

from . import dtos

import logging

logger = logging.getLogger(__name__)


@controller("Session")
class SessionHandler(BaseHandler):
    def __init__(
        self,
        torrent_repo: TorrentRepository = Closing[Provide[RepoContainer.torrent_repo]],
        peer_repo: PeerRepository = Closing[Provide[RepoContainer.peer_repo]],
    ):
        super().__init__()
        self.torrent_repo = torrent_repo
        self.peer_repo = peer_repo

    @create(dtos.HANDSHAKE_DATASET)
    async def handshake(
        self,
        peer_id: str,
        info_hash: str,
        protocol_version: str,
    ):
        # Si no conocemos el torrent, no aceptamos el handshake
        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            logger.warning(f"Handshake rechazado: Info_hash {info_hash} no encontrado")
            raise ValueError("Info hash not found")

        logger.info(f"Handshake recibido para peer {peer_id} del torrent {info_hash}")

        now = datetime.now(timezone.utc)

        # Obtener o crear el peer (en la tabla 'peers')
        peer = await self.peer_repo.get_by_identifier(peer_id)
        if not peer:
            logger.info(f"Nuevo peer detectado: {peer_id}")
            peer = PeerTable(
                peer_identifier=peer_id,
                ip="0.0.0.0",
                port=0,
                last_announce=now,
                protocol_version=protocol_version,
            )
            await self.peer_repo.add(peer)
        else:
            logger.info(f"Actualizando peer conocido: {peer_id}")
            peer.last_announce = now
            await self.peer_repo.update(peer)

        # Aquí es donde usas tu tabla intermedia
        is_linked = await self.torrent_repo.is_peer_in_torrent(info_hash, peer_id)
        if not is_linked:
            logger.info(f"Vinculando peer {peer_id} al torrent {info_hash}")
            await self.torrent_repo.add_peer_to_torrent(info_hash, peer_id)
        else:
            logger.info("El peer ya estaba vinculado a este torrent.")

        return HandshakeSuccess(
            message="Handshake exitoso",
            protocol_version=protocol_version,
        )

    @delete(dtos.DISCONNECT_DATASET)
    async def disconnect(
        self,
        peer_id: str,
        info_hash: str,
    ):
        logger.info(f"Petición de desconexión: Peer {peer_id} -> Torrent {info_hash}")

        peer = await self.peer_repo.get_by_identifier(peer_id)
        if not peer:
            # Si el peer no existe, ya está "desconectado" técnicamente.
            return DisconnectSuccess(message="Peer no existía o ya estaba desconectado")

        torrent = await self.torrent_repo.get(info_hash)
        if not torrent:
            # Si el torrent no existe, la relación en torrent_peers ya debería haber
            # desaparecido por el ON DELETE CASCADE que definiste.
            return DisconnectSuccess(
                message="Torrent no encontrado, asumiendo limpieza exitosa"
            )

        # Remover peer del torrent usando los identificadores correctos
        await self.torrent_repo.remove_peer_from_torrent(info_hash, peer_id)

        logger.info(f"Vínculo eliminado: Peer {peer_id} ya no participa en {info_hash}")

        return DisconnectSuccess(message="Peer desconectado exitosamente del torrent")

    @update(dtos.KEEPALIVE_DATASET)
    async def keepalive(
        self,
        peer_id: str,
    ):
        logger.info(f"Received keepalive for peer {peer_id}")

        # Es más eficiente hacer un UPDATE directo por ID que un GET + UPDATE.
        updated_peer = await self.peer_repo.update_peer_activity(peer_id)

        if not updated_peer:
            # Si el repositorio devuelve None o lanza error porque no existe el ID
            raise NotFoundError(peer_id, res_type="Peer")

        now = datetime.now(timezone.utc)

        return DataResponse(
            message=f"Peer {peer_id} activity updated",
            data={
                "last_announce": now.isoformat(),
                "peer_id": peer_id,
            }
        )
