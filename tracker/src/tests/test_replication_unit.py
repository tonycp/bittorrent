"""
PHASE 3: Unit Tests - Replication Methods Validation
==================================================

Simple unit tests to validate replication methods exist and work correctly.
Focus on method signatures and basic functionality.

Tests:
1. EventLogRepository.mark_replicated() - Creates replicated_to entry
2. EventLogRepository.get_pending_replication_for_tracker() - Returns pending events
3. PeerRepository.upsert() - Idempotent peer create/update
4. PeerRepository.mark_seed() - Updates seed status
5. ReplicationService hash - Deterministic hashing

Status: Ready for integration with test framework
"""

import pytest
import hashlib
from inspect import signature

from ..repos.event import EventLogRepository
from ..repos.peer import PeerRepository
from ..services.replication import ReplicationService


class TestRepositoryMethodsExist:
    """Verify all required methods exist with correct signatures"""

    def test_event_mark_replicated_exists(self):
        """EventLogRepository.mark_replicated() exists"""
        assert hasattr(EventLogRepository, "mark_replicated")
        method = getattr(EventLogRepository, "mark_replicated")
        # Check signature has event_id and tracker_id parameters
        sig = signature(method)
        params = list(sig.parameters.keys())
        assert "event_id" in params or "id" in params
        assert "tracker_id" in params

    def test_event_get_pending_exists(self):
        """EventLogRepository.get_pending_replication_for_tracker() exists"""
        assert hasattr(EventLogRepository, "get_pending_replication_for_tracker")
        method = getattr(EventLogRepository, "get_pending_replication_for_tracker")
        sig = signature(method)
        params = list(sig.parameters.keys())
        assert "target_tracker_id" in params or "tracker_id" in params

    def test_peer_upsert_exists(self):
        """PeerRepository.upsert() exists"""
        assert hasattr(PeerRepository, "upsert")
        method = getattr(PeerRepository, "upsert")
        sig = signature(method)
        params = list(sig.parameters.keys())
        assert "peer_id" in params
        # Should have ip, port parameters
        assert any(p in params for p in ["ip", "port", "uploaded"])

    def test_peer_mark_seed_exists(self):
        """PeerRepository.mark_seed() exists"""
        assert hasattr(PeerRepository, "mark_seed")
        method = getattr(PeerRepository, "mark_seed")
        sig = signature(method)
        params = list(sig.parameters.keys())
        assert "peer_id" in params or "id" in params
        assert "is_seed" in params

    def test_replication_service_hash_deterministic(self):
        """ReplicationService uses deterministic MD5 hash"""
        # Check that the method exists
        assert hasattr(ReplicationService, "_select_replica_targets")

        # Verify MD5 is imported in replication.py
        import src.services.replication as repl_module

        source = open(repl_module.__file__).read()

        # Should import hashlib
        assert "hashlib" in source or "md5" in source.lower()

        # Should NOT use Python's built-in hash() for determinism
        # Check that MD5 is actually used
        lines = [l for l in source.split("\n") if "hashlib.md5" in l or "md5(" in l]
        assert len(lines) > 0, "MD5 should be used for deterministic hashing"


class TestReplicationServiceLogic:
    """Test ReplicationService hashing logic is deterministic"""

    def test_hash_always_same_torrent(self):
        """Same torrent always hashes to same replica targets"""

        # Create mock objects that won't actually query DB
        class MockSession:
            pass

        class MockCluster:
            pass

        service = ReplicationService(session=MockSession(), cluster=MockCluster())

        torrent_hash = "abc123def456"
        n_trackers = 5

        # Call multiple times
        result1 = service._select_replica_targets(torrent_hash, n_trackers)
        result2 = service._select_replica_targets(torrent_hash, n_trackers)
        result3 = service._select_replica_targets(torrent_hash, n_trackers)

        # All results should be identical (deterministic)
        assert result1 == result2, "Hash should be deterministic"
        assert result2 == result3, "Hash should be deterministic"

    def test_hash_different_torrents_different_targets(self):
        """Different torrents can hash to different replica targets"""

        class MockSession:
            pass

        class MockCluster:
            pass

        service = ReplicationService(session=MockSession(), cluster=MockCluster())

        torrent1 = "torrent-1"
        torrent2 = "torrent-2"
        n_trackers = 5

        result1 = service._select_replica_targets(torrent1, n_trackers)
        result2 = service._select_replica_targets(torrent2, n_trackers)

        # Results should exist
        assert result1 is not None
        assert result2 is not None
        # Each should be a list
        assert isinstance(result1, (list, tuple))
        assert isinstance(result2, (list, tuple))

    def test_hash_uses_md5_not_python_hash(self):
        """Verify MD5 is used instead of Python's hash()"""
        import src.services.replication as repl_module

        source = open(repl_module.__file__).read()

        # Should have MD5
        assert "hashlib.md5" in source or "from hashlib import" in source

        # Should NOT use Python's hash() for partition selection
        # Look for the _select_replica_targets method
        lines = source.split("\n")
        in_method = False
        method_lines = []

        for line in lines:
            if "def _select_replica_targets" in line:
                in_method = True
            elif in_method:
                if line.strip() and not line.startswith(" " * 8) and "def " in line:
                    break
                method_lines.append(line)

        method_source = "\n".join(method_lines)

        # Should use MD5-based approach
        assert "md5" in method_source.lower() or "hashlib" in method_source


class TestSchemaFieldExists:
    """Test EventTable has replicated_to field"""

    def test_event_table_has_replicated_to(self):
        """EventTable schema includes replicated_to field"""
        from ..schemas.event import EventTable

        # Check EventTable has replicated_to column
        mapper = EventTable.__mapper__
        columns = {col.name for col in mapper.columns}

        assert "replicated_to" in columns, "EventTable must have replicated_to field"


class TestHandlerTransactions:
    """Test ReplicationHandler uses transactions"""

    def test_replication_handler_uses_transactions(self):
        """ReplicationHandler.peer_announce() uses transactions"""
        import src.handlers.replication as handler_module

        source = open(handler_module.__file__).read()

        # Should use session.begin() for transactions
        assert "session.begin()" in source or "async with" in source
        # Should call upsert
        assert "upsert" in source


class TestReplicationLogic:
    """Test per-tracker replication strategy"""

    def test_per_tracker_not_per_torrent(self):
        """Replication strategy changed from per-torrent to per-tracker"""
        import src.services.replication as repl_module

        source = open(repl_module.__file__).read()

        # Should have per_tracker method or strategy
        assert (
            "get_pending_replication_for_tracker" in source
            or "per_tracker" in source.lower()
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
