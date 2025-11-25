from advanced_alchemy.config import SQLAlchemyAsyncConfig
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    async_scoped_session,
)
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from tracker.schemas import EntityTable
from asyncio import current_task


class Database:
    """Clase Database que envuelve Advanced Alchemy con control granular"""

    def __init__(
        self,
        db_url: str,
        echo: bool,
        pool_size: int,
        max_overflow: int,
        pool_recycle: int,
    ) -> None:
        self._engine = create_async_engine(
            db_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
        )
        self._config = SQLAlchemyAsyncConfig(engine_instance=self._engine)
        self._session_factory = async_scoped_session(
            async_sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            ),
            current_task,
        )

    @property
    def engine(self):
        """Acceso al engine subyacente"""
        return self._engine

    @property
    def config(self):
        """Acceso a la configuración de Advanced Alchemy"""
        return self._config

    def get_session_factory(self):
        """Retorna la session factory para inyección en repositorios"""
        return self._session_factory

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager asíncrono para sesiones"""
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

    # Métodos de gestión de base de datos
    async def create_database_async(self) -> None:
        """Crea todas las tablas de forma asíncrona"""
        async with self._engine.begin() as conn:
            await conn.run_sync(EntityTable.metadata.create_all)

    async def drop_database_async(self) -> None:
        """Elimina todas las tablas de forma asíncrona"""
        async with self._engine.begin() as conn:
            await conn.run_sync(EntityTable.metadata.drop_all)

    async def health_check_async(self) -> bool:
        """Verifica la salud de la base de datos (async)"""
        try:
            async with self.async_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def dispose_async(self) -> None:
        """Libera recursos (async)"""
        if hasattr(self, "_engine"):
            await self._engine.dispose()

    @property
    def metadata(self):
        """Acceso a los metadatos"""
        return EntityTable.metadata
