#!/usr/bin/env python3
"""Script de prueba básica del cliente"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.client.connection.tracker_client import TrackerClient


async def test_tracker_connection():
    """Prueba conexión básica con tracker"""
    print("=" * 60)
    print("TEST: Conexión con Tracker")
    print("=" * 60)
    
    client = TrackerClient()
    await client.start()
    
    # Generar hash único
    import time
    import hashlib
    torrent_hash = hashlib.sha256(f"test{time.time()}".encode()).hexdigest()[:16]
    
    # Test 1: Registrar torrent
    print("\n[1] Registrando torrent de prueba...")
    print(f"    Hash: {torrent_hash}")
    success = await client.register_torrent(
        tracker_host="localhost",
        tracker_port=5555,
        torrent_hash=torrent_hash,
        file_name="test_file.bin",
        file_size=1048576,
        total_chunks=64,
        piece_length=16384,
    )
    
    if success:
        print("✅ Torrent registrado exitosamente")
    else:
        print("❌ Error registrando torrent")
        return False
    
    # Test 2: Announce peer
    print("\n[2] Anunciando peer...")
    result = await client.announce_peer(
        tracker_host="localhost",
        tracker_port=5555,
        tracker_id="tracker-1",
        peer_id="test-peer-001",
        torrent_hash=torrent_hash,
        ip="192.168.1.100",
        port=6881,
        uploaded=0,
        downloaded=0,
        left=1048576,
    )
    
    if result:
        print("✅ Announce exitoso")
        print(f"   Respuesta: {result}")
    else:
        print("❌ Error en announce")
        return False
    
    # Test 3: Obtener peers
    print("\n[3] Obteniendo lista de peers...")
    peers = await client.get_peers(
        tracker_host="localhost",
        tracker_port=5555,
        torrent_hash=torrent_hash,
    )
    
    if peers is not None:
        print(f"✅ Obtenidos {len(peers)} peers")
        for peer in peers:
            print(f"   - Peer: {peer.get('peer_id', 'N/A')} @ {peer.get('ip')}:{peer.get('port')}")
    else:
        print("❌ Error obteniendo peers")
        return False
    
    await client.stop()
    
    print("\n" + "=" * 60)
    print("✅ TODOS LOS TESTS PASARON")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_tracker_connection())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
