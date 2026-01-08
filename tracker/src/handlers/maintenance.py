"""Handler para tareas de mantenimiento y limpieza"""

from datetime import datetime, UTC, timedelta

from dependency_injector.wiring import Provide

from bit_lib.handlers import BaseMaintenanceHandler
from bit_lib.handlers.crud import update
from bit_lib.tools.controller import controller
from bit_lib.models import DataResponse

from src.repos import RepoContainer, PeerRepository, TorrentRepository, EventLogRepository, TrackerRepository


@controller("Maintenance")
class MaintenanceHandler(BaseMaintenanceHandler):
    def __init__(
        self,
        peer_repo: PeerRepository = Provide[RepoContainer.peer_repo],
        torrent_repo: TorrentRepository = Provide[RepoContainer.torrent_repo],
        event_repo: EventLogRepository = Provide[RepoContainer.event_log_repo],
        tracker_repo: TrackerRepository = Provide[RepoContainer.tracker_repo],
    ):
        super().__init__()
        self.peer_repo = peer_repo
        self.torrent_repo = torrent_repo
        self.event_repo = event_repo
        self.tracker_repo = tracker_repo

    @update()
    async def cleanup_peers(self, max_inactive_minutes: int = 30):
        removed = await self.peer_repo.remove_inactive_peers(max_inactive_minutes)
        return DataResponse(data={"removed_peers": removed, "max_inactive_minutes": max_inactive_minutes})

    @update()
    async def cleanup_torrents(self):
        removed = await self.torrent_repo.remove_orphaned_torrents()
        return DataResponse(data={"removed_torrents": removed})

    @update()
    async def cleanup_events(self, retention_minutes: int = 10):
        cutoff_time = datetime.now(UTC) - timedelta(minutes=retention_minutes)
        cutoff_ts = int(cutoff_time.timestamp())
        removed = await self.event_repo.purge_old_events(cutoff_ts)
        return DataResponse(data={"removed_events": removed, "retention_minutes": retention_minutes})

    @update()
    async def remove_dead_trackers(self, ttl_minutes: int = 60):
        cutoff_time = datetime.now(UTC) - timedelta(minutes=ttl_minutes)
        removed = await self.tracker_repo.remove_inactive_trackers(cutoff_time)
        return DataResponse(data={"removed_count": removed, "ttl_minutes": ttl_minutes})
