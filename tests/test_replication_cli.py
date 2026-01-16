#!/usr/bin/env python3
"""
TEST SIMPLE: Replicación entre 2 trackers
==========================================

Usa el CLI del cliente para:
1. Crear un torrent en tracker-1 (localhost:5555)
2. Anunciar un peer
3. Consultar tracker-2 (localhost:5557) para verificar que se replicó
"""

import asyncio
import sys
from pathlib import Path

# Add client to path
sys.path.insert(0, str(Path(__file__).parent.parent / "client"))
from cli_simple import BitTorrentClientCLI
from bit_lib.models import Request


async def main():
    print("=" * 80)
    print("TEST DE REPLICACIÓN ENTRE TRACKERS")
    print("=" * 80)

    # Cliente apuntando a tracker-1
    client1 = BitTorrentClientCLI()
    client1.tracker_host = "localhost"
    client1.tracker_port = 5555

    # Cliente apuntando a tracker-2
    client2 = BitTorrentClientCLI()
    client2.tracker_host = "localhost"
    client2.tracker_port = 5557

    # TEST 1: Crear torrent en tracker-1
    print("\n[1] Creando torrent en tracker-1 (localhost:5555)...")
    ok = await client1.create_torrent("test-file.bin", 1048576, 10)

    if not ok:
        print("❌ Error creando torrent")
        return 1

    torrent_hash = list(client1.registered_torrents.keys())[0]
    print(f"✅ Torrent creado con hash: {torrent_hash}")

    # TEST 2: Anunciar peer en tracker-1
    print("\n[2] Anunciando peer en tracker-1...")
    ok = await client1.announce_peer(
        torrent_hash, peer_id="peer-001", ip="192.168.1.100", port=6881, event="started"
    )

    if not ok:
        print("❌ Error anunciando peer")
        return 1

    print("✅ Peer anunciado en tracker-1")

    # TEST 3: Esperar replicación
    print("\n[3] Esperando replicación (20 segundos para permitir discovery y replicación)...")
    await asyncio.sleep(20)

    # TEST 4: Consultar peers en tracker-2
    print("\n[4] Consultando peers en tracker-2 (localhost:5557)...")

    req = Request(
        controller="Bit",
        command="get",
        func="peer_list",
        args={"info_hash": torrent_hash},
    )

    try:
        response = await client2.request("localhost", 5557, req, timeout=5)

        if response and response.data:
            # Acceder a data que puede ser dict o objeto
            if isinstance(response.data, dict):
                inner_data = response.data.get("data", response.data)
            else:
                inner_data = getattr(response.data, "data", response.data)
            
            # Ahora inner_data tiene los peers
            if isinstance(inner_data, dict):
                peers = inner_data.get("peers", [])
            else:
                peers = getattr(inner_data, "peers", [])
                
            print(f"✅ Tracker-2 retornó {len(peers)} peer(s)")

            if len(peers) > 0:
                print(f"   Peer encontrado: {peers[0]}")
                print("\n🎉 ¡REPLICACIÓN FUNCIONANDO!")
                return 0
            else:
                print("\n❌ No se encontraron peers en tracker-2")
                print("   La replicación no funcionó")
                return 1
        else:
            print("❌ No hay datos en la respuesta de tracker-2")
            return 1

    except Exception as e:
        print(f"❌ Error consultando tracker-2: {e}")
        print(f"   Tipo: {type(e).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
