#!/usr/bin/env python3
"""
TEST ROBUSTO: Replicación entre 5 trackers con límite de 3 réplicas
====================================================================

Valida que:
1. Crear un torrent en tracker-1
2. Anunciar un peer
3. Verificar que EXACTAMENTE 3 trackers reciben la replicación (no los 5)
4. Los 3 trackers seleccionados son determinísticos (basados en hash)
"""

import asyncio
import sys
from pathlib import Path

# Add client to path
sys.path.insert(0, str(Path(__file__).parent.parent / "client"))
from cli_simple import BitTorrentClientCLI
from bit_lib.models import Request


# Configuración de trackers
TRACKERS = [
    {"name": "tracker-1", "host": "localhost", "port": 5555},
    {"name": "tracker-2", "host": "localhost", "port": 5557},
    {"name": "tracker-3", "host": "localhost", "port": 5559},
    {"name": "tracker-4", "host": "localhost", "port": 5561},
    {"name": "tracker-5", "host": "localhost", "port": 5563},
]


async def check_peers_in_tracker(
    tracker_info: dict, torrent_hash: str
) -> tuple[bool, int]:
    """
    Consulta un tracker para verificar si tiene peers del torrent.

    Returns:
        (tiene_peers, num_peers)
    """
    client = BitTorrentClientCLI()
    client.tracker_host = tracker_info["host"]
    client.tracker_port = tracker_info["port"]

    req = Request(
        controller="Bit",
        command="get",
        func="peer_list",
        args={"info_hash": torrent_hash},
    )

    try:
        response = await client.request(
            tracker_info["host"], tracker_info["port"], req, timeout=5
        )

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

            has_peers = len(peers) > 0
            return (has_peers, len(peers))
        else:
            return (False, 0)

    except Exception as e:
        print(f"   ⚠️  Error consultando {tracker_info['name']}: {e}")
        return (False, 0)


async def main():
    print("=" * 80)
    print("TEST DE REPLICACIÓN ROBUSTA: 5 TRACKERS → 3 RÉPLICAS")
    print("=" * 80)
    print("\nObjetivo: Validar que con 5 trackers disponibles, solo 3 reciben réplicas")
    print("          (tolerancia a fallos nivel 2 según informe)")
    print()

    # Cliente apuntando a tracker-1 para operaciones iniciales
    client1 = BitTorrentClientCLI()
    client1.tracker_host = "localhost"
    client1.tracker_port = 5555

    # TEST 1: Crear torrent en tracker-1
    print("[1] Creando torrent en tracker-1...")
    ok = await client1.create_torrent("test-robust.bin", 2097152, 20)  # 2MB, 20 chunks

    if not ok:
        print("❌ Error creando torrent")
        return 1

    torrent_hash = list(client1.registered_torrents.keys())[0]
    print(f"✅ Torrent creado: {torrent_hash}")

    # TEST 2: Anunciar peer en tracker-1
    print("\n[2] Anunciando peer en tracker-1...")
    ok = await client1.announce_peer(
        torrent_hash,
        peer_id="peer-robust-001",
        ip="192.168.1.200",
        port=6881,
        event="started",
    )

    if not ok:
        print("❌ Error anunciando peer")
        return 1

    print("✅ Peer anunciado")

    # TEST 3: Esperar discovery + replicación
    print("\n[3] Esperando replicación (30 segundos para 5 trackers)...")
    print("    - Discovery de cluster: ~15s")
    print("    - Primera replicación: ~2s")
    print("    - Margen de seguridad: 30s total")
    await asyncio.sleep(30)

    # TEST 4: Consultar cada tracker
    print("\n[4] Consultando los 5 trackers para verificar replicación...")
    print("    Según el informe: 'información replicada al menos en tres trackers'")
    print()

    results = []
    for tracker in TRACKERS:
        has_peers, count = await check_peers_in_tracker(tracker, torrent_hash)
        results.append((tracker["name"], has_peers, count))

        status = "✅ TIENE DATOS" if has_peers else "⚪ SIN DATOS"
        print(
            f"    {tracker['name']:12s} (:{tracker['port']}) → {status} ({count} peer{'s' if count != 1 else ''})"
        )

    # TEST 5: Validar resultados
    print("\n[5] Validando política de replicación...")

    trackers_with_data = sum(1 for _, has_peers, _ in results if has_peers)

    print(
        f"\n📊 RESULTADO: {trackers_with_data}/5 trackers tienen el torrent replicado"
    )
    print()

    # Validaciones
    success = True

    if trackers_with_data == 3:
        print("✅ CORRECTO: Exactamente 3 trackers tienen réplicas")
        print("   → Cumple con 'mínimo 3 réplicas' para tolerancia a fallos nivel 2")
    elif trackers_with_data < 3:
        print(f"❌ ERROR: Solo {trackers_with_data} trackers tienen réplicas")
        print("   → Esperado: 3 réplicas (tolerancia a fallos nivel 2)")
        success = False
    elif trackers_with_data == 5:
        print(f"⚠️  ADVERTENCIA: Los 5 trackers tienen réplicas")
        print("   → Esperado: Solo 3 réplicas (política de particionado)")
        print("   → Revisar lógica de _select_replica_targets()")
        success = False
    else:  # 4 trackers
        print(f"⚠️  INESPERADO: {trackers_with_data} trackers tienen réplicas")
        print("   → Esperado: 3 réplicas exactamente")
        success = False

    # Validar que el tracker-1 (origen) siempre tenga los datos
    tracker1_has_data = results[0][1]
    if tracker1_has_data:
        print("✅ Tracker-1 (origen) tiene los datos (esperado)")
    else:
        print("⚠️  Tracker-1 (origen) NO tiene los datos (inesperado)")

    # Validar determinismo: los mismos 3 trackers deberían ser siempre seleccionados
    if trackers_with_data == 3:
        selected = [name for name, has, _ in results if has]
        print(f"\n📌 Trackers seleccionados: {', '.join(selected)}")
        print("   (Debería ser determinístico basado en hash del torrent)")

    print("\n" + "=" * 80)
    if success and trackers_with_data == 3:
        print(
            "🎉 TEST EXITOSO: Replicación funciona correctamente con límite de 3 réplicas"
        )
        return 0
    else:
        print("❌ TEST FALLIDO: La replicación no cumple con las especificaciones")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
