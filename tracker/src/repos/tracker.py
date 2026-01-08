from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from bit_lib.context import VectorClock
from src.models.tracker import Tracker
from src.schemas.tracker import TrackerTable


class TrackerRepository(SQLAlchemyAsyncRepository[TrackerTable]):
    """Repositorio para gestionar trackers en la red distribuida."""
    
    model_type = TrackerTable

    async def upsert(self, tracker: Tracker) -> Tracker:
        """
        Crea o actualiza un tracker.
        
        Args:
            tracker: modelo Tracker
        
        Returns:
            El tracker persistido
        """
        stmt = select(TrackerTable).where(TrackerTable.tracker_id == tracker.tracker_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Actualizar (advanced_alchemy actualiza updated_at automáticamente)
            existing.host = tracker.host
            existing.port = tracker.port
            existing.status = tracker.status
            # Convertir VectorClock a dict para almacenamiento
            existing.vector_clock = tracker.vector_clock.to_dict()
            await self.update(existing)
        else:
            # Crear
            table_obj = TrackerTable(
                tracker_id=tracker.tracker_id,
                host=tracker.host,
                port=tracker.port,
                status=tracker.status,
                vector_clock=tracker.vector_clock.to_dict(),
            )
            await self.add(table_obj)
            await self.session.flush()
        
        return tracker

    async def get_by_tracker_id(self, tracker_id: str) -> Tracker | None:
        """Obtiene un tracker por su tracker_id."""
        stmt = select(TrackerTable).where(TrackerTable.tracker_id == tracker_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        
        if row:
            return self._row_to_tracker(row)
        return None

    async def get_active_trackers(self, ttl_minutes: int = 30) -> list[Tracker]:
        """
        Obtiene trackers activos en los últimos N minutos.
        
        Args:
            ttl_minutes: minutos de vida útil
        
        Returns:
            Lista de trackers con status 'online' y updated_at reciente
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
        stmt = select(TrackerTable).where(
            (TrackerTable.status == "online") &
            (TrackerTable.updated_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        
        return [self._row_to_tracker(row) for row in rows]

    async def get_all(self) -> list[Tracker]:
        """Obtiene todos los trackers."""
        stmt = select(TrackerTable)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        
        return [self._row_to_tracker(row) for row in rows]

    async def update_last_seen(self, tracker_id: str) -> bool:
        """
        Actualiza el último contacto de un tracker.
        
        Returns:
            True si se actualizó, False si no existe
        """
        stmt = select(TrackerTable).where(TrackerTable.tracker_id == tracker_id)
        result = await self.session.execute(stmt)
        tracker = result.scalar_one_or_none()
        
        if tracker:
            # Solo cambiar status; advanced_alchemy actualiza updated_at automáticamente
            tracker.status = "online"
            await self.update(tracker)
            return True
        return False

    async def mark_inactive(self, tracker_id: str) -> bool:
        """Marca un tracker como offline."""
        stmt = select(TrackerTable).where(TrackerTable.tracker_id == tracker_id)
        result = await self.session.execute(stmt)
        tracker = result.scalar_one_or_none()
        
        if tracker:
            tracker.status = "offline"
            await self.update(tracker)
            return True
        return False

    async def remove_dead_trackers(self, ttl_minutes: int = 60) -> int:
        """
        Elimina trackers offline o sin contacto por más de N minutos.
        
        Args:
            ttl_minutes: minutos sin contacto antes de eliminar
        
        Returns:
            Cantidad de trackers eliminados
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
        stmt = select(TrackerTable).where(
            (TrackerTable.status == "offline") |
            (TrackerTable.updated_at < cutoff)
        )
        result = await self.session.execute(stmt)
        dead_trackers = result.scalars().all()
        
        count = 0
        for tracker in dead_trackers:
            await self.delete(tracker.id)
            count += 1
        
        await self.session.commit()
        return count

    def _row_to_tracker(self, row: TrackerTable) -> Tracker:
        """Convierte fila de BD a modelo Tracker."""
        return Tracker(
            id=row.id,
            version=row.version,
            created_at=row.created_at,
            updated_at=row.updated_at,
            tracker_id=row.tracker_id,
            host=row.host,
            port=row.port,
            status=row.status,
            vector_clock=VectorClock.from_dict(row.vector_clock) if row.vector_clock else VectorClock(),
        )
