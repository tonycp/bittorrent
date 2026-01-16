"""
Servicio P2P para transferencia de chunks entre clientes.

Combina HostService (servidor) y ClientService (cliente) para permitir
tanto servir chunks propios como solicitar chunks de otros peers.
"""

import asyncio
import hashlib
import logging
import os
from typing import Optional, Dict

from bit_lib.services import HostService, ClientService
from bit_lib.models import Request, Response, MetaData, BlockInfo, Error
from bit_lib.proto.protocol import MProtocol
from bit_lib.proto.collector import BlockCollector
from bit_lib.const import c_proto as cp

logger = logging.getLogger(__name__)


class PeerService(HostService, ClientService):
    """
    Servicio P2P que permite a un cliente:
    - Servir chunks a otros peers (HostService)
    - Solicitar chunks de otros peers (ClientService)
    """

    def __init__(self, downloads_path: str, loop: asyncio.AbstractEventLoop, host: str = "0.0.0.0", port: int = 6881):
        # Inicializar servicios base
        HostService.__init__(self, host=host, port=port)
        ClientService.__init__(self)
        
        # Usar el loop proporcionado en lugar del default
        self.loop = loop
        
        self.downloads_path = downloads_path
        self.chunk_size = 256 * 1024  # 256 KB
        
        # Cache de torrents activos (file_hash -> file_path)
        self._active_files: Dict[str, str] = {}
        
        # Collectors para chunks en descarga
        self._chunk_collectors: Dict[str, BlockCollector] = {}

    def register_file(self, file_hash: str, file_path: str):
        """Registra un archivo que puede ser servido a otros peers"""
        self._active_files[file_hash] = file_path
        logger.info(f"Archivo registrado para seeding: {file_hash[:8]} -> {os.path.basename(file_path)}")

    def unregister_file(self, file_hash: str):
        """Desregistra un archivo"""
        if file_hash in self._active_files:
            del self._active_files[file_hash]
            logger.info(f"Archivo desregistrado: {file_hash[:8]}")

    # ==================== Request Handlers (Server Side) ====================

    async def _handle_request(self, protocol: MProtocol, request: Request):
        """Maneja solicitudes de chunks de otros peers"""
        try:
            if request.controller == "Chunk" and request.func == "get":
                await self._handle_chunk_request(protocol, request)
            else:
                logger.warning(f"Solicitud no soportada: {request.controller}:{request.func}")
                error = Error(
                    reply_to=request.msg_id,
                    data={"error": f"Unknown request: {request.controller}:{request.func}"}
                )
                await self.send_message(protocol, error)
        except Exception as e:
            logger.error(f"Error manejando request: {e}", exc_info=True)
            error = Error(
                reply_to=request.msg_id,
                data={"error": str(e)}
            )
            await self.send_message(protocol, error)

    async def _handle_chunk_request(self, protocol: MProtocol, request: Request):
        """
        Maneja solicitud de chunk.
        
        Request args:
            torrent_hash: str - Hash del archivo
            chunk_index: int - Índice del chunk solicitado
        """
        args = request.args or {}
        torrent_hash = args.get("torrent_hash")
        chunk_index = args.get("chunk_index")

        if not torrent_hash or chunk_index is None:
            error = Error(
                reply_to=request.msg_id,
                data={"error": "Missing torrent_hash or chunk_index"}
            )
            await self.send_message(protocol, error)
            return

        # Verificar que tenemos el archivo
        if torrent_hash not in self._active_files:
            error = Error(
                reply_to=request.msg_id,
                data={"error": f"Torrent {torrent_hash[:8]} not found"}
            )
            await self.send_message(protocol, error)
            return

        file_path = self._active_files[torrent_hash]

        try:
            # Leer chunk del archivo
            chunk_data = await self._read_chunk(file_path, chunk_index)
            
            if chunk_data is None:
                error = Error(
                    reply_to=request.msg_id,
                    data={"error": f"Chunk {chunk_index} not available"}
                )
                await self.send_message(protocol, error)
                return

            # Calcular hash del chunk
            chunk_hash = hashlib.sha1(chunk_data).hexdigest()

            # Enviar chunk como datos binarios
            metadata = MetaData(
                index=chunk_index,
                hash=chunk_hash,
                total=len(chunk_data)
            )
            metadata.msg_id = request.msg_id  # Usar mismo msg_id para tracking

            logger.debug(
                f"Enviando chunk {chunk_index} de {torrent_hash[:8]} "
                f"({len(chunk_data)} bytes) a peer"
            )

            await self.send_binary(protocol, metadata, chunk_data)

        except Exception as e:
            logger.error(f"Error sirviendo chunk {chunk_index}: {e}", exc_info=True)
            error = Error(
                reply_to=request.msg_id,
                data={"error": str(e)}
            )
            await self.send_message(protocol, error)

    async def _read_chunk(self, file_path: str, chunk_index: int) -> Optional[bytes]:
        """Lee un chunk específico del archivo"""
        try:
            if not os.path.exists(file_path):
                return None

            offset = chunk_index * self.chunk_size

            # Ejecutar I/O en thread pool para no bloquear event loop
            loop = asyncio.get_event_loop()
            chunk_data = await loop.run_in_executor(
                None,
                self._read_chunk_sync,
                file_path,
                offset,
                self.chunk_size
            )

            return chunk_data

        except Exception as e:
            logger.error(f"Error leyendo chunk {chunk_index} de {file_path}: {e}")
            return None

    @staticmethod
    def _read_chunk_sync(file_path: str, offset: int, size: int) -> bytes:
        """Lee chunk de forma síncrona (para executor)"""
        with open(file_path, "rb") as f:
            f.seek(offset)
            return f.read(size)

    # ==================== Client Side (Request Chunks) ====================

    async def request_chunk(
        self,
        peer_host: str,
        peer_port: int,
        torrent_hash: str,
        chunk_index: int,
        timeout: float = 30.0
    ) -> Optional[bytes]:
        """
        Solicita un chunk específico a un peer.
        
        Returns:
            bytes del chunk si se descargó exitosamente, None si falló
        """
        try:
            req = Request(
                controller="Chunk",
                command="get",
                func="get",
                args={
                    "torrent_hash": torrent_hash,
                    "chunk_index": chunk_index
                }
            )

            logger.debug(
                f"Solicitando chunk {chunk_index} de {torrent_hash[:8]} "
                f"a {peer_host}:{peer_port}"
            )

            # Crear collector para este chunk
            collector_key = f"{torrent_hash}_{chunk_index}"
            
            # Conectar y enviar request
            protocol = await self.connect(peer_host, peer_port)
            await self.send_message(protocol, req)

            # Esperar respuesta binaria
            # El chunk llegará vía _handle_binary
            # Crear future para esperar
            future = asyncio.Future()
            self._chunk_collectors[collector_key] = {
                "future": future,
                "msg_id": req.msg_id
            }

            try:
                chunk_data = await asyncio.wait_for(future, timeout=timeout)
                logger.debug(
                    f"Chunk {chunk_index} descargado exitosamente "
                    f"({len(chunk_data) if chunk_data else 0} bytes)"
                )
                return chunk_data
            finally:
                # Limpiar collector
                if collector_key in self._chunk_collectors:
                    del self._chunk_collectors[collector_key]

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout descargando chunk {chunk_index} de {peer_host}:{peer_port}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Error solicitando chunk {chunk_index} de {peer_host}:{peer_port}: {e}",
                exc_info=True
            )
            return None

    # ==================== Binary Handlers (Receive Chunks) ====================

    async def _handle_binary(self, protocol: MProtocol, meta: MetaData, data: bytes):
        """
        Recibe chunk binario de un peer.
        
        MetaData contiene:
            index: int - Índice del chunk
            hash: str - Hash SHA1 del chunk
            total: int - Tamaño total del chunk
            msg_id: str - ID del request original
        """
        try:
            chunk_index = meta.index
            chunk_hash = meta.hash
            total_size = meta.total

            # Verificar hash
            calculated_hash = hashlib.sha1(data).hexdigest()
            if calculated_hash != chunk_hash:
                logger.error(
                    f"Hash mismatch para chunk {chunk_index}: "
                    f"esperado {chunk_hash[:8]}, recibido {calculated_hash[:8]}"
                )
                return

            logger.debug(
                f"Chunk {chunk_index} recibido y verificado "
                f"({len(data)} bytes, hash OK)"
            )

            # Buscar future esperando este chunk
            # Nota: necesitamos mejorar el tracking con msg_id
            for collector_key, collector_data in list(self._chunk_collectors.items()):
                if collector_data.get("msg_id") == meta.msg_id:
                    future = collector_data.get("future")
                    if future and not future.done():
                        future.set_result(data)
                    break

        except Exception as e:
            logger.error(f"Error en _handle_binary: {e}", exc_info=True)

    # ==================== Response/Error Handlers ====================

    async def _handle_response(self, protocol: MProtocol, response: Response):
        """Maneja responses generales (no chunks binarios)"""
        # Los chunks se manejan vía _handle_binary
        logger.debug(f"Response recibido: {response.msg_id}")

    async def _handle_error(self, protocol: MProtocol, error: Error):
        """Maneja errores de peers"""
        logger.error(f"Error de peer: {error.data}")
        
        # Completar future con None si hay error
        reply_to = error.reply_to
        for collector_key, collector_data in list(self._chunk_collectors.items()):
            if collector_data.get("msg_id") == reply_to:
                future = collector_data.get("future")
                if future and not future.done():
                    future.set_result(None)
                break

    # ==================== Connection Handlers ====================

    async def _on_connect(self, protocol: MProtocol):
        """Callback cuando se establece conexión"""
        logger.debug("Peer conectado")

    async def _on_disconnect(self, protocol: MProtocol, exc: Optional[Exception]):
        """Callback cuando se cierra conexión"""
        if exc:
            logger.debug(f"Peer desconectado con error: {exc}")
        else:
            logger.debug("Peer desconectado")
