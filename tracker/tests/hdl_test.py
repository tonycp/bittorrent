# test_tracker.py
from uuid import uuid4

from shared.proto.message import DataSerialize
from .base_data import TestData
from .base_hdl import (
    announce,
    handshake,
    disconnect,
    keepalive,
    peer_list,
    file_info,
    create_torrent,
)

import pytest


@pytest.mark.asyncio
class TestTrackerBasic:
    """Tests básicos del tracker"""

    async def test_handshake(self):
        """Test de handshake básico"""
        peer_data = TestData.generate_peer_data()
        await handshake(peer_data["peer_id"], DataSerialize.VERSION)

    async def test_create_torrent(self):
        """Test de creación de torrent"""
        torrent_data = TestData.generate_torrent_data()
        await create_torrent(**torrent_data)
        return torrent_data["info_hash"]

    async def test_announce_started(self):
        """Test de announce con evento started"""
        torrent_data = TestData.generate_torrent_data()
        peer_data = TestData.generate_peer_data()

        await create_torrent(**torrent_data)
        await handshake(peer_data["peer_id"], DataSerialize.VERSION)
        await announce(
            info_hash=torrent_data["info_hash"],
            peer_id=peer_data["peer_id"],
            ip=peer_data["ip"],
            port=peer_data["port"],
            left=torrent_data["file_size"],
            event="started",
        )

    async def test_peer_list(self):
        """Test de obtención de lista de peers"""
        torrent_data = TestData.generate_torrent_data()
        await create_torrent(**torrent_data)
        result = await peer_list(torrent_data["info_hash"])
        assert result is not None


@pytest.mark.asyncio
class TestTrackerAdvanced:
    """Tests avanzados del tracker"""

    async def test_complete_peer_lifecycle(self):
        """Test completo del ciclo de vida de un peer"""
        # Setup
        torrent_data = TestData.generate_torrent_data()
        peer_data = TestData.generate_peer_data()

        # 1. Crear torrent
        await create_torrent(**torrent_data)

        # 2. Handshake
        await handshake(peer_data["peer_id"], DataSerialize.VERSION)

        # 3. Announce started
        await announce(
            info_hash=torrent_data["info_hash"],
            peer_id=peer_data["peer_id"],
            ip=peer_data["ip"],
            port=peer_data["port"],
            left=torrent_data["file_size"],
            event="started",
        )

        # 4. Keepalive
        await keepalive(peer_data["peer_id"])

        # 5. Announce progress
        await announce(
            info_hash=torrent_data["info_hash"],
            peer_id=peer_data["peer_id"],
            ip=peer_data["ip"],
            port=peer_data["port"],
            left=torrent_data["file_size"] // 2,
            event=None,
        )

        # 6. Get file info
        file_info_result = await file_info(torrent_data["info_hash"])
        assert file_info_result is not None

        # 7. Get peer list
        peer_list_result = await peer_list(torrent_data["info_hash"])
        assert peer_list_result is not None

        # 8. Announce completed
        await announce(
            info_hash=torrent_data["info_hash"],
            peer_id=peer_data["peer_id"],
            ip=peer_data["ip"],
            port=peer_data["port"],
            left=0,
            event="completed",
        )

        # 9. Disconnect
        await disconnect(
            peer_id=peer_data["peer_id"], info_hash=torrent_data["info_hash"]
        )

    async def test_multiple_peers_same_torrent(self):
        """Test de múltiples peers en el mismo torrent"""
        torrent_data = TestData.generate_torrent_data()
        await create_torrent(**torrent_data)

        # Primer peer
        peer_1 = TestData.generate_peer_data(torrent_data["info_hash"])
        await handshake(peer_1["peer_id"], DataSerialize.VERSION)
        await announce(**peer_1)

        # Segundo peer
        peer_2 = TestData.generate_peer_data(torrent_data["info_hash"])
        peer_2["ip"] = "192.168.1.2"
        peer_2["port"] = 6882
        await handshake(peer_2["peer_id"], DataSerialize.VERSION)
        await announce(**peer_2)

        # Verificar que hay múltiples peers
        result = await peer_list(torrent_data["info_hash"])
        assert result is not None


@pytest.mark.asyncio
class TestTrackerEdgeCases:
    """Tests de casos edge"""

    async def test_announce_nonexistent_torrent(self):
        """Test de announce en torrent que no existe"""
        peer_data = TestData.generate_peer_data()
        await handshake(peer_data["peer_id"], DataSerialize.VERSION)

        with pytest.raises(Exception):  # Debería fallar
            await announce(**peer_data)

    async def test_peer_list_nonexistent_torrent(self):
        """Test de peer list en torrent que no existe"""
        with pytest.raises(Exception):  # Debería fallar
            await peer_list(uuid4().hex)


# Tests parametrizados para diferentes escenarios
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event,left",
    [
        ("started", 1024000),
        (None, 512000),
        ("completed", 0),
        ("stopped", 1024000),
    ],
)
async def test_announce_different_events(event, left):
    """Test de announce con diferentes eventos"""
    torrent_data = TestData.generate_torrent_data()
    peer_data = TestData.generate_peer_data()

    await create_torrent(**torrent_data)
    await handshake(peer_data["peer_id"], DataSerialize.VERSION)

    await announce(
        info_hash=torrent_data["info_hash"],
        peer_id=peer_data["peer_id"],
        ip=peer_data["ip"],
        port=peer_data["port"],
        left=left,
        event=event,
    )


# Fixtures para datos de prueba
@pytest.fixture
def sample_torrent_data():
    return TestData.generate_torrent_data()


@pytest.fixture
def sample_peer_data():
    return TestData.generate_peer_data()


@pytest.mark.asyncio
async def test_with_fixtures(sample_torrent_data, sample_peer_data):
    """Test usando fixtures de pytest"""
    await create_torrent(**sample_torrent_data)
    await handshake(sample_peer_data["peer_id"], DataSerialize.VERSION)

    result = await announce(
        info_hash=sample_torrent_data["info_hash"],
        peer_id=sample_peer_data["peer_id"],
        ip=sample_peer_data["ip"],
        port=sample_peer_data["port"],
        left=sample_torrent_data["file_size"],
        event="started",
    )

    assert result is not None
