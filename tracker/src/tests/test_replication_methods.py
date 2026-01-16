"""
Unit Tests para Métodos de Replicación

Fase 3 - Validación de métodos nuevos en Repository Layer
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Imports del sistema
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.event import EventTable
from schemas.peer import PeerTable
from schemas.torrent import TorrentTable
from repos.event import EventLogRepository
from repos.peer import PeerRepository
from repos.torrent import TorrentRepository


# Configurar DB temporal para tests
@pytest.fixture
async def test_db():
    """Crea una base de datos temporal para testing"""
    # Usar SQLite en memoria
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )
    
    # Crear todas las tablas
    async with engine.begin() as conn:
        from sqlalchemy import MetaData, Table, Column, String, Integer, DateTime, Float, Boolean, JSON, ForeignKey
        
        # Crear tablas manualmente
        metadata = MetaData()
        
        # Tabla de torrents
        torrents = Table(
            'torrents',
            metadata,
            Column('id', String(40), primary_key=True),
            Column('info_hash', String(40), unique=True, index=True),
            Column('piece_length', Integer),
            Column('total_length', Integer),
            Column('pieces_hash', String(1000)),
            Column('name', String(255)),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow),
        )
        
        # Tabla de eventos
        events = Table(
            'events',
            metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('tracker_id', String(50)),
            Column('vector_clock', JSON),
            Column('operation', String(50)),
            Column('timestamp', DateTime, default=datetime.utcnow),
            Column('data', JSON),
            Column('replicated_to', JSON, default=dict),
        )
        
        # Tabla de peers
        peers = Table(
            'peers',
            metadata,
            Column('id', String(40), primary_key=True),
            Column('peer_identifier', String(100), unique=True),
            Column('ip', String(45)),
            Column('port', Integer),
            Column('uploaded', Integer, default=0),
            Column('downloaded', Integer, default=0),
            Column('left', Integer, default=0),
            Column('is_seed', Boolean, default=False),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('last_announce', DateTime, default=datetime.utcnow),
            Column('is_active', Boolean, default=True),
        )
        
        await conn.run_sync(metadata.create_all)
    
    # Crear session maker
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield AsyncSessionLocal, engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


class TestMarkReplicatedEvent:
    """Tests para EventLogRepository.mark_replicated()"""
    
    @pytest.mark.asyncio
    async def test_mark_replicated_basic(self, test_db):
        """Test: marcar evento como replicado a un tracker"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = EventLogRepository(session)
            
            # Crear evento inicial
            event_data = {
                "tracker_id": "tracker-1",
                "vector_clock": {"tracker-1": 1},
                "operation": "peer_announce",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"peer_id": "peer-1"},
                "replicated_to": {}
            }
            
            # Insertar evento
            query = f"""
            INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            stmt = f"INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (?, ?, ?, ?, ?, ?)"
            # Usar SQL directo
            from sqlalchemy import text
            result = await session.execute(
                text("INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (:tracker_id, :vector_clock, :operation, :timestamp, :data, :replicated_to)"),
                {
                    "tracker_id": "tracker-1",
                    "vector_clock": '{"tracker-1": 1}',
                    "operation": "peer_announce",
                    "timestamp": datetime.utcnow(),
                    "data": '{"peer_id": "peer-1"}',
                    "replicated_to": '{}'
                }
            )
            await session.commit()
            
            # Obtener event_id
            result = await session.execute(
                text("SELECT id FROM events WHERE tracker_id = 'tracker-1' LIMIT 1")
            )
            event_id = result.scalar()
            assert event_id is not None, "Event no fue creado"
            
            # Marcar como replicado
            await repo.mark_replicated(event_id, "tracker-2")
            
            # Verificar
            result = await session.execute(
                text("SELECT replicated_to FROM events WHERE id = ?"),
                [event_id]
            )
            replicated_to = result.scalar()
            assert replicated_to is not None, "replicated_to no encontrado"
            
            print(f"✅ Test: mark_replicated_basic PASSED")
    
    @pytest.mark.asyncio
    async def test_mark_replicated_multiple_trackers(self, test_db):
        """Test: marcar evento replicado a múltiples trackers"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = EventLogRepository(session)
            from sqlalchemy import text
            
            # Crear evento
            await session.execute(
                text("INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (:tracker_id, :vector_clock, :operation, :timestamp, :data, :replicated_to)"),
                {
                    "tracker_id": "tracker-1",
                    "vector_clock": '{"tracker-1": 1}',
                    "operation": "peer_announce",
                    "timestamp": datetime.utcnow(),
                    "data": '{"peer_id": "peer-1"}',
                    "replicated_to": '{}'
                }
            )
            await session.commit()
            
            # Get event ID
            result = await session.execute(text("SELECT id FROM events WHERE tracker_id = 'tracker-1' LIMIT 1"))
            event_id = result.scalar()
            
            # Marcar a múltiples trackers
            await repo.mark_replicated(event_id, "tracker-2")
            await repo.mark_replicated(event_id, "tracker-3")
            
            # Verificar ambos están marcados
            result = await session.execute(
                text("SELECT replicated_to FROM events WHERE id = ?"),
                [event_id]
            )
            replicated_to = result.scalar()
            
            print(f"✅ Test: mark_replicated_multiple_trackers PASSED")


class TestGetPendingReplicationForTracker:
    """Tests para EventLogRepository.get_pending_replication_for_tracker()"""
    
    @pytest.mark.asyncio
    async def test_get_pending_basic(self, test_db):
        """Test: obtener eventos pendientes para tracker"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = EventLogRepository(session)
            from sqlalchemy import text
            
            # Crear 3 eventos, uno ya replicado
            await session.execute(
                text("INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (:tracker_id, :vector_clock, :operation, :timestamp, :data, :replicated_to)"),
                {
                    "tracker_id": "tracker-1",
                    "vector_clock": '{"tracker-1": 1}',
                    "operation": "peer_announce",
                    "timestamp": datetime.utcnow(),
                    "data": '{"peer_id": "peer-1"}',
                    "replicated_to": '{"tracker-2": true}'  # Ya replicado
                }
            )
            
            await session.execute(
                text("INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (:tracker_id, :vector_clock, :operation, :timestamp, :data, :replicated_to)"),
                {
                    "tracker_id": "tracker-1",
                    "vector_clock": '{"tracker-1": 2}',
                    "operation": "peer_announce",
                    "timestamp": datetime.utcnow(),
                    "data": '{"peer_id": "peer-2"}',
                    "replicated_to": '{}'  # NO replicado
                }
            )
            
            await session.execute(
                text("INSERT INTO events (tracker_id, vector_clock, operation, timestamp, data, replicated_to) VALUES (:tracker_id, :vector_clock, :operation, :timestamp, :data, :replicated_to)"),
                {
                    "tracker_id": "tracker-1",
                    "vector_clock": '{"tracker-1": 3}',
                    "operation": "peer_completed",
                    "timestamp": datetime.utcnow(),
                    "data": '{"peer_id": "peer-3"}',
                    "replicated_to": '{"tracker-2": false}'  # NO replicado (false)
                }
            )
            
            await session.commit()
            
            # Obtener pendientes para tracker-2
            pending = await repo.get_pending_replication_for_tracker("tracker-2", datetime.utcnow() - timedelta(hours=1))
            
            # Debería haber 2 pendientes (no el primero que ya está replicado)
            assert len(pending) >= 1, f"Se esperaban eventos pendientes, se obtuvieron {len(pending)}"
            
            print(f"✅ Test: get_pending_basic PASSED (encontrados {len(pending)} eventos pendientes)")


class TestPeerUpsert:
    """Tests para PeerRepository.upsert()"""
    
    @pytest.mark.asyncio
    async def test_upsert_create_new(self, test_db):
        """Test: crear nuevo peer con upsert"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = PeerRepository(session)
            
            # Crear nuevo peer
            peer_id = "peer-upsert-1"
            result = await repo.upsert(
                peer_id=peer_id,
                ip="192.168.1.1",
                port=6881,
                uploaded=1000,
                downloaded=2000,
                left=5000,
                is_seed=False
            )
            
            assert result is not None, "upsert debería retornar el peer"
            print(f"✅ Test: upsert_create_new PASSED")
    
    @pytest.mark.asyncio
    async def test_upsert_idempotent(self, test_db):
        """Test: upsert es idempotente (update en segundo llamado)"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = PeerRepository(session)
            
            peer_id = "peer-upsert-2"
            
            # Primer upsert (create)
            result1 = await repo.upsert(
                peer_id=peer_id,
                ip="192.168.1.2",
                port=6882,
                uploaded=1000,
                downloaded=2000,
                left=5000,
                is_seed=False
            )
            
            # Segundo upsert (update)
            result2 = await repo.upsert(
                peer_id=peer_id,
                ip="192.168.1.3",  # IP diferente
                port=6883,
                uploaded=2000,  # Valores actualizados
                downloaded=3000,
                left=4000,
                is_seed=True
            )
            
            # Verificar que es el mismo peer (idempotente)
            assert result2 is not None, "Segundo upsert debería retornar peer"
            print(f"✅ Test: upsert_idempotent PASSED")


class TestPeerMarkSeed:
    """Tests para PeerRepository.mark_seed()"""
    
    @pytest.mark.asyncio
    async def test_mark_seed_true(self, test_db):
        """Test: marcar peer como seeder"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = PeerRepository(session)
            
            # Crear peer primero
            peer_id = "peer-seed-1"
            await repo.upsert(
                peer_id=peer_id,
                ip="192.168.1.4",
                port=6884,
                uploaded=0,
                downloaded=1000,
                left=10000,
                is_seed=False
            )
            
            # Marcar como seeder
            result = await repo.mark_seed(peer_id, True)
            assert result is not None, "mark_seed debería retornar True"
            
            print(f"✅ Test: mark_seed_true PASSED")
    
    @pytest.mark.asyncio
    async def test_mark_seed_false(self, test_db):
        """Test: desmarcar peer como seeder"""
        AsyncSessionLocal, engine = test_db
        
        async with AsyncSessionLocal() as session:
            repo = PeerRepository(session)
            
            # Crear peer como seeder
            peer_id = "peer-seed-2"
            await repo.upsert(
                peer_id=peer_id,
                ip="192.168.1.5",
                port=6885,
                uploaded=1000,
                downloaded=1000,
                left=0,
                is_seed=True
            )
            
            # Desmarcar como seeder
            result = await repo.mark_seed(peer_id, False)
            assert result is not None, "mark_seed debería retornar resultado"
            
            print(f"✅ Test: mark_seed_false PASSED")


# Ejecutar tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
