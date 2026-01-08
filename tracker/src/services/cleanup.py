import asyncio
import logging
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)


class CleanupService:
    """Servicio para limpieza periódica de peers inactivos y eventos antiguos"""

    def __init__(
        self,
        peer_repo,
        torrent_repo,
        event_repo,
        interval: int = 300,
        peer_ttl_minutes: int = 30,
        event_retention_minutes: int = 10,
    ):
        self.peer_repo = peer_repo
        self.torrent_repo = torrent_repo
        self.event_repo = event_repo
        self.interval = interval
        self.peer_ttl_minutes = peer_ttl_minutes
        self.event_retention_minutes = event_retention_minutes
        
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start_cleanup_loop(self):
        """Inicia el loop periódico de limpieza"""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup loop started")

    async def stop_cleanup_loop(self):
        """Detiene el loop de limpieza"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cleanup loop stopped")

    async def _cleanup_loop(self):
        """Loop principal que ejecuta limpieza periódicamente"""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._perform_cleanup()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _perform_cleanup(self):
        """Ejecuta todas las tareas de limpieza"""
        try:
            # Limpiar peers inactivos
            removed_peers = await self.peer_repo.remove_inactive_peers(
                max_inactive_minutes=self.peer_ttl_minutes
            )
            if removed_peers > 0:
                logger.info(f"Removed {removed_peers} inactive peers")
            
            # Limpiar torrents huérfanos
            removed_torrents = await self.torrent_repo.remove_orphaned_torrents()
            if removed_torrents > 0:
                logger.info(f"Removed {removed_torrents} orphaned torrents")
            
            # Limpiar eventos antiguos
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.event_retention_minutes)
            cutoff_ts = int(cutoff_time.timestamp())
            removed_events = await self.event_repo.purge_old_events(cutoff_ts)
            if removed_events > 0:
                logger.info(f"Purged {removed_events} old events")
        
        except Exception as e:
            logger.error(f"Error performing cleanup: {e}")
