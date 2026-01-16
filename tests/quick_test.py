#!/usr/bin/env python3
"""Quick test para validar replicación básica"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "client"))
from cli_simple import BitTorrentClientCLI
from bit_lib.models import Request

TRACKERS = [
    {"name": "tracker-1", "host": "localhost", "port": 5555},
    {"name": "tracker-2", "host": "localhost", "port": 5557},
    {"name": "tracker-3", "host": "localhost", "port": 5559},
    {"name": "tracker-4", "host": "localhost", "port": 5561},
    {"name": "tracker-5", "host": "localhost", "port": 5563},
    {"name": "tracker-6", "host": "localhost", "port": 5565},
]

async def check_peers(tracker_info, torrent_hash):
    """Check if tracker has peers for torrent"""
    try:
        client = BitTorrentClientCLI()
        req = Request(
            controller="Bit",
            command="get",
            func="peer_list",
            args={"info_hash": torrent_hash},
        )
        response = await client.request(
            tracker_info["host"], tracker_info["port"], req, timeout=5
        )
        
        if response and response.data:
            data = response.data.get("data", response.data) if isinstance(response.data, dict) else response.data
            peers = data.get("peers", []) if isinstance(data, dict) else getattr(data, "peers", [])
            return len(peers)
        return 0
    except Exception as e:
        return -1  # Error


async def main():
    print("=" * 60)
    print("QUICK REPLICATION TEST")
    print("=" * 60)
    
    # Create torrent on tracker-1
    print("\n[1] Creating torrent on tracker-1...")
    client = BitTorrentClientCLI()
    client.tracker_host = "localhost"
    client.tracker_port = 5555
    
    ok = await client.create_torrent("quick-test.bin", 1048576, 10)
    if not ok:
        print("❌ Failed to create torrent")
        return
    
    torrent_hash = list(client.registered_torrents.keys())[0]
    print(f"✅ Torrent created: {torrent_hash}")
    
    # Announce peer
    print("\n[2] Announcing peer...")
    ok = await client.announce_peer(
        torrent_hash,
        peer_id="peer-quick-test",
        ip="192.168.1.100",
        port=6881,
        event="started",
    )
    if not ok:
        print("❌ Failed to announce")
        return
    print("✅ Peer announced")
    
    # Wait for replication
    print("\n[3] Waiting 15s for replication...")
    await asyncio.sleep(15)
    
    # Check replicas
    print("\n[4] Checking replicas...")
    replicas = []
    for tracker in TRACKERS:
        peer_count = await check_peers(tracker, torrent_hash)
        if peer_count > 0:
            replicas.append(tracker["name"])
            print(f"  {tracker['name']:12s} → ✅ {peer_count} peer(s)")
        elif peer_count == 0:
            print(f"  {tracker['name']:12s} → ⚪ No data")
        else:
            print(f"  {tracker['name']:12s} → ❌ Error")
    
    print(f"\n{'='*60}")
    print(f"RESULT: {len(replicas)} replicas found")
    print(f"Replicas: {', '.join(replicas)}")
    
    if len(replicas) == 3:
        print("✅ PASS: Exactly 3 replicas as expected")
    else:
        print(f"⚠️  WARNING: Expected 3 replicas, got {len(replicas)}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
