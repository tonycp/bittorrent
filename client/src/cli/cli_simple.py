#!/usr/bin/env python3
"""
CLI Minimalista para client - Usa bit_lib directamente
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Logging
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from bit_lib.services import ClientService
from bit_lib.models import Request


class BitTorrentClientCLI(ClientService):
    """Cliente BitTorrent minimalista usando bit_lib"""

    def __init__(self):
        super().__init__()
        self.tracker_host = "localhost"
        self.tracker_port = 5555
        self.registered_torrents: Dict[str, Dict[str, Any]] = {}
        self.peer_id = "CLIENT-001"
        self.protocol_version = "1.0"

    # ==================== Métodos Abstractos ====================

    async def _handle_request(self, protocol, req: Request):
        """No recibimos requests (somos cliente)"""
        logger.warning(f"Received unexpected request: {req}")
        return None

    async def _handle_binary(self, protocol, meta, data: bytes):
        """No recibimos datos binarios"""
        pass

    async def _on_connect(self, protocol):
        logger.debug("Connected to tracker")

    async def _on_disconnect(self, protocol, exc: Optional[Exception]):
        logger.debug(f"Disconnected from tracker: {exc}")

    # ==================== Operaciones de Torrent ====================

    async def create_torrent(self, name: str, size: int, chunks: int) -> bool:
        """Crea un torrent en el tracker"""
        import hashlib
        import time

        # Generar hash del torrent con timestamp para garantizar unicidad
        torrent_hash = hashlib.sha256(
            f"{name}{size}{chunks}{time.time()}".encode()
        ).hexdigest()[:16]

        # Calcular piece_length basado en size/chunks
        piece_length = max(16384, size // chunks) if chunks > 0 else 16384

        try:
            logger.info(
                f"Creando torrent: {name} ({size} bytes, {chunks} chunks, piece_length={piece_length})"
            )

            req = Request(
                controller="Register",
                command="create",
                func="create_torrent",
                args={
                    "info_hash": torrent_hash,
                    "file_name": name,
                    "file_size": size,
                    "total_chunks": chunks,
                    "piece_length": piece_length,
                },
            )

            response = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )

            if response and response.data:
                self.registered_torrents[torrent_hash] = {
                    "name": name,
                    "size": size,
                    "chunks": chunks,
                    "hash": torrent_hash,
                }
                logger.info(f"✅ Torrent creado: {torrent_hash}")
                return True
            else:
                logger.error(f"❌ Fallo al crear torrent")
                return False

        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            return False

    async def handshake(self, info_hash: str, peer_id: Optional[str] = None) -> bool:
        """Realiza handshake contra el tracker (Session:create)."""
        pid = peer_id or self.peer_id
        req = Request(
            controller="Session",
            command="create",
            func="handshake",
            args={
                "peer_id": pid,
                "info_hash": info_hash,
                "protocol_version": self.protocol_version,
            },
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info("✅ Handshake OK")
                return True
            logger.error(f"❌ Handshake sin data: {resp}")
            return False
        except Exception as e:
            logger.error(f"❌ Handshake error: {e}", exc_info=True)
            return False

    async def announce_peer(
        self,
        torrent_hash: str,
        peer_id: Optional[str] = None,
        ip: str = "127.0.0.1",
        port: int = 6881,
        left: Optional[int] = None,
        event: str = "started",
    ) -> bool:
        """Announce directo al handler Bit (no Event/replicación)."""
        pid = peer_id or self.peer_id
        remaining = (
            left
            if left is not None
            else self.registered_torrents.get(torrent_hash, {}).get("size", 0)
        )
        req = Request(
            controller="Bit",
            command="create",
            func="announce",
            args={
                "info_hash": torrent_hash,
                "peer_id": pid,
                "ip": ip,
                "port": port,
                "left": remaining,
                "event": event,
            },
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info("✅ Announce OK")
                return True
            logger.error(f"❌ Announce sin data: {resp}")
            return False
        except Exception as e:
            logger.error(f"❌ Announce error: {e}", exc_info=True)
            return False

    async def peer_list(self, torrent_hash: str):
        req = Request(
            controller="Bit",
            command="get",
            func="peer_list",
            args={"info_hash": torrent_hash},
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info(f"✅ Peer list OK")
                return resp.data
            logger.error(f"❌ Peer list sin respuesta")
            return None
        except Exception as e:
            logger.error(f"❌ Peer list error: {e}", exc_info=True)
            return None

    async def scrape(self, torrent_hash: str):
        req = Request(
            controller="Bit",
            command="get",
            func="scrape",
            args={"info_hash": torrent_hash},
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info(f"✅ Scrape OK")
                return resp.data
            logger.error(f"❌ Scrape sin respuesta")
            return None
        except Exception as e:
            logger.error(f"❌ Scrape error: {e}", exc_info=True)
            return None

    async def keepalive(self, peer_id: Optional[str] = None):
        pid = peer_id or self.peer_id
        req = Request(
            controller="Session",
            command="update",
            func="keepalive",
            args={"peer_id": pid},
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info(f"✅ Keepalive OK: {resp.data}")
                return resp.data
            logger.error(f"❌ Keepalive sin respuesta")
            return None
        except Exception as e:
            logger.error(f"❌ Keepalive error: {e}", exc_info=True)
            return None

    async def disconnect(self, torrent_hash: str, peer_id: Optional[str] = None):
        pid = peer_id or self.peer_id
        req = Request(
            controller="Session",
            command="delete",
            func="disconnect",
            args={"peer_id": pid, "info_hash": torrent_hash},
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info(f"✅ Disconnect OK: {resp.data}")
                return resp.data
            logger.error(f"❌ Disconnect sin respuesta")
            return None
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}", exc_info=True)
            return None

    async def file_info(self, torrent_hash: str):
        req = Request(
            controller="Register",
            command="get",
            func="file_info",
            args={"info_hash": torrent_hash},
        )
        try:
            resp = await self.request(
                self.tracker_host, self.tracker_port, req, timeout=10
            )
            if resp and resp.data:
                logger.info(f"✅ File info OK")
                return resp.data
            logger.error(f"❌ File info sin respuesta")
            return None
        except Exception as e:
            logger.error(f"❌ File info error: {e}", exc_info=True)
            return None

    async def list_torrents(self):
        """Lista los torrents registrados"""
        if not self.registered_torrents:
            print("No hay torrents registrados")
            return

        print("\n📦 Torrents Registrados:")
        print("─" * 80)
        for hash_val, info in self.registered_torrents.items():
            print(f"  • {info['name']}")
            print(f"    Hash: {hash_val}")
            print(f"    Size: {info['size']} bytes")
            print(f"    Chunks: {info['chunks']}")
            print()

    async def show_status(self):
        """Muestra estado actual"""
        print(f"\n📊 Estado del Cliente:")
        print("─" * 80)
        print(f"  Tracker: {self.tracker_host}:{self.tracker_port}")
        print(f"  Torrents: {len(self.registered_torrents)}")
        print()


async def interactive_cli():
    """CLI interactivo"""
    client = BitTorrentClientCLI()

    print("""
╔════════════════════════════════════════════╗
║   BitTorrent Client CLI (bit_lib)          ║
║   Commands: create, announce, list, exit   ║
╚════════════════════════════════════════════╝
""")

    while True:
        try:
            cmd = input("\n> ").strip().lower()

            if cmd == "exit" or cmd == "quit":
                print("👋 Saliendo...")
                break

            elif cmd == "status":
                await client.show_status()

            elif cmd == "list":
                await client.list_torrents()

            elif cmd == "create":
                name = input("  Nombre del archivo: ").strip()
                try:
                    size = int(input("  Tamaño en bytes: ").strip())
                    chunks = int(input("  Número de chunks: ").strip())
                    success = await client.create_torrent(name, size, chunks)
                    if success:
                        print("✅ Torrent creado exitosamente")
                except ValueError:
                    print("❌ Valores inválidos")

            elif cmd == "announce":
                if not client.registered_torrents:
                    print("❌ No hay torrents registrados. Usa 'create' primero.")
                    continue

                print("\nTorrents disponibles:")
                torrents = list(client.registered_torrents.items())
                for i, (hash_val, info) in enumerate(torrents):
                    print(f"  {i + 1}. {info['name']} ({hash_val})")

                try:
                    idx = int(input("  Selecciona número: ").strip()) - 1
                    torrent_hash = torrents[idx][0]
                    peer_id = (
                        input("  Peer ID (ej: CLIENT-001): ").strip() or client.peer_id
                    )
                    event = (
                        input(
                            "  Evento (started/completed/stopped) [started]: "
                        ).strip()
                        or "started"
                    )
                    left = client.registered_torrents[torrent_hash]["size"]

                    # Handshake previo
                    await client.handshake(peer_id)
                    success = await client.announce_peer(
                        torrent_hash,
                        peer_id=peer_id,
                        event=event,
                        left=left,
                    )
                    if success:
                        print("✅ Announce exitoso")
                except (ValueError, IndexError):
                    print("❌ Selección inválida")

            elif cmd == "handshake":
                pid = input("  Peer ID [CLIENT-001]: ").strip() or client.peer_id
                await client.handshake(pid)

            elif cmd == "peers":
                if not client.registered_torrents:
                    print("❌ No hay torrents registrados.")
                    continue
                torrents = list(client.registered_torrents.items())
                for i, (hash_val, info) in enumerate(torrents):
                    print(f"  {i + 1}. {info['name']} ({hash_val})")
                try:
                    idx = int(input("  Selecciona número: ").strip()) - 1
                    torrent_hash = torrents[idx][0]
                    data = await client.peer_list(torrent_hash)
                    print(json.dumps(data, indent=2, default=str))
                except (ValueError, IndexError):
                    print("❌ Selección inválida")

            elif cmd == "scrape":
                if not client.registered_torrents:
                    print("❌ No hay torrents registrados.")
                    continue
                torrents = list(client.registered_torrents.items())
                for i, (hash_val, info) in enumerate(torrents):
                    print(f"  {i + 1}. {info['name']} ({hash_val})")
                try:
                    idx = int(input("  Selecciona número: ").strip()) - 1
                    torrent_hash = torrents[idx][0]
                    data = await client.scrape(torrent_hash)
                    print(json.dumps(data, indent=2, default=str))
                except (ValueError, IndexError):
                    print("❌ Selección inválida")

            elif cmd == "keepalive":
                pid = input("  Peer ID [CLIENT-001]: ").strip() or client.peer_id
                data = await client.keepalive(pid)
                print(data)

            elif cmd == "disconnect":
                if not client.registered_torrents:
                    print("❌ No hay torrents registrados.")
                    continue
                torrents = list(client.registered_torrents.items())
                for i, (hash_val, info) in enumerate(torrents):
                    print(f"  {i + 1}. {info['name']} ({hash_val})")
                try:
                    idx = int(input("  Selecciona número: ").strip()) - 1
                    torrent_hash = torrents[idx][0]
                    pid = input("  Peer ID [CLIENT-001]: ").strip() or client.peer_id
                    data = await client.disconnect(torrent_hash, pid)
                    print(data)
                except (ValueError, IndexError):
                    print("❌ Selección inválida")

            elif cmd == "fileinfo":
                if not client.registered_torrents:
                    print("❌ No hay torrents registrados.")
                    continue
                torrents = list(client.registered_torrents.items())
                for i, (hash_val, info) in enumerate(torrents):
                    print(f"  {i + 1}. {info['name']} ({hash_val})")
                try:
                    idx = int(input("  Selecciona número: ").strip()) - 1
                    torrent_hash = torrents[idx][0]
                    data = await client.file_info(torrent_hash)
                    print(json.dumps(data, indent=2, default=str))
                except (ValueError, IndexError):
                    print("❌ Selección inválida")

            elif cmd == "help":
                print("""
Comandos disponibles:
  create     - Crear nuevo torrent en el tracker
  announce   - Anunciar este peer para un torrent
  handshake  - Handshake con el tracker (Session)
  peers      - Listar peers del torrent (peer_list)
  scrape     - Obtener estadísticas del torrent (seeders/leechers)
  keepalive  - Enviar keepalive para un peer
  disconnect - Desconectar un peer del torrent
  fileinfo   - Obtener información del torrent
  list       - Listar torrents registrados
  status     - Ver estado actual del cliente
  help       - Mostrar esta ayuda
  exit/quit  - Salir
""")

            else:
                if cmd:
                    print(f"❌ Comando desconocido: {cmd}")

        except KeyboardInterrupt:
            print("\n👋 Saliendo...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(interactive_cli())
