from .interfaces.track_interface import *
from ..core.bsc_hds import controller
from ..core.crud_hds import create, update, delete, get, get_all
from ..repos.repository import GenericRepository
from ..schema.torrent import Torrent, Peer
from sqlalchemy.orm import Session
from datetime import datetime, timezone


@controller()
class TrackerController:
    def __init__(self, session: Session):
        self.session = session
        self.peer_repo = GenericRepository(session, Peer)
        self.torrent_repo = GenericRepository(session, Torrent)

    @create(ANNOUNCE_DATASET)
    def announce(
        self,
        info_hash: str,
        peer_id: str,
        ip: str,
        port: int,
        uploaded: int,
        downloaded: int,
        left: int,
        event: str = None,  # Agregado para manejar eventos BT
    ):
        # Buscar el torrent
        torrent = self.torrent_repo.get_by_field(info_hash=info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        # Buscar el peer
        peer = self.peer_repo.get_by_field(peer_id=peer_id)
        now = datetime.now(timezone.utc)

        if not peer:
            peer = Peer(
                peer_id=peer_id,
                ip=ip,
                port=port,
                uploaded=uploaded,
                downloaded=downloaded,
                left=left,
                last_announce=now,
                is_seed=(event == "completed"),
            )
            self.peer_repo.add(peer)
            torrent.peers.append(peer)
        else:
            peer.ip = ip
            peer.port = port
            peer.uploaded = uploaded
            peer.downloaded = downloaded
            peer.left = left
            peer.last_announce = now
            if event == "completed":
                peer.is_seed = True
            if event == "stopped":
                if peer in torrent.peers:
                    torrent.peers.remove(peer)  # O marcar el peer para limpieza

        # Listar peers activos (limpia los inactivos: ejemplo, en los últimos 2 x interval)
        interval = 1800
        active_peers = [
            {"ip": p.ip, "port": p.port}
            for p in torrent.peers
            if p.last_announce
            and (now - p.last_announce).total_seconds() < 2 * interval
        ]

        return {
            "interval": interval,
            "peers": active_peers,
        }

    @create(HANDSHAKE_DATASET)
    def handshake(self, peer_id: str, client_name: str, protocol_version: str):
        # Opcional: validar versión de protocolo
        if protocol_version != "1.0":
            raise ValueError("Versión de protocolo no soportada")

        now = datetime.now(timezone.utc)
        # Buscar o crear el peer
        peer = self.peer_repo.get_by_field(peer_id=peer_id)
        if not peer:
            peer = Peer(
                peer_id=peer_id,
                ip="0.0.0.0",  # Puedes actualizar luego si lo tienes
                port=0,
                uploaded=0,
                downloaded=0,
                left=0,
                last_announce=now,
                is_seed=False,
                client_name=client_name,
                protocol_version=protocol_version,
            )
            self.peer_repo.add(peer)
        else:
            peer.client_name = client_name
            peer.protocol_version = protocol_version
            peer.last_announce = now

        return {
            "status": "ok",
            "message": "Handshake exitoso",
            "protocol_version": protocol_version,
        }

    @create(DISCONNECT_DATASET)  # Debes definir este decorator/dataset para DISCONNECT
    def disconnect(self, peer_id: str, info_hash: str):
        torrent = self.torrent_repo.get_by_field(info_hash=info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        peer = self.peer_repo.get_by_field(peer_id=peer_id)
        if not peer:
            raise ValueError("Peer no encontrado")

        # Elimina el peer de la lista del torrent
        if peer in torrent.peers:
            torrent.peers.remove(peer)
            self.peer_repo.delete(peer)  # Si deseas borrarlo completamente
            return {"status": "ok", "message": "Peer desconectado"}
        else:
            return {"status": "not_found", "message": "Peer no asociado al torrent"}

    @create(KEEPALIVE_DATASET)
    def keepalive(self, peer_id: str):
        peer = self.peer_repo.get_by_field(peer_id=peer_id)
        if not peer:
            raise ValueError("Peer no encontrado")

        now = datetime.now(timezone.utc)
        peer.last_announce = now  # Solo actualiza el timestamp de actividad

        return {"status": "ok", "message": "Seguimiento de actividad actualizado"}

    @get(PEER_LIST_DATASET)
    def peer_list(self, info_hash: str):
        torrent = self.torrent_repo.get_by_field(info_hash=info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        now = datetime.now(timezone.utc)
        interval = 1800
        active_peers = [
            {"peer_id": p.peer_id, "ip": p.ip, "port": p.port}
            for p in torrent.peers
            if p.last_announce
            and (now - p.last_announce).total_seconds() < 2 * interval
        ]

        return {"info_hash": info_hash, "peers": active_peers}

    @get(GET_PEERS_DATASET)
    def scrape(self, info_hash: str):
        torrent = self.torrent_repo.get_by_field(info_hash=info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        now = datetime.now(timezone.utc)
        interval = 1800
        active_peers = [
            p
            for p in torrent.peers
            if p.last_announce
            and (now - p.last_announce).total_seconds() < 2 * interval
        ]
        seeders = sum(1 for p in active_peers if getattr(p, "is_seed", False))
        leechers = len(active_peers) - seeders

        return {"info_hash": info_hash, "seeders": seeders, "leechers": leechers}

    @get(FILE_INFO_DATASET)
    def file_info(self, info_hash: str):
        torrent = self.torrent_repo.get_by_field(info_hash=info_hash)
        if not torrent:
            raise ValueError("Torrent no encontrado")

        return {
            "info_hash": info_hash,
            "file_name": torrent.file_name,
            "file_size": torrent.file_size,
            "total_chunks": torrent.total_chunks,
        }
