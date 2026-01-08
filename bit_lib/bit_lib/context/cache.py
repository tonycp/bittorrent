import asyncio
import time
import logging
from typing import TypeVar, Generic, Optional, Dict

T = TypeVar('T')
logger = logging.getLogger(__name__)


class CacheEntry(Generic[T]):
    """Entrada individual en caché con timestamp y valor."""
    
    def __init__(self, value: T, ttl_seconds: int):
        self.value = value
        self.ttl = ttl_seconds
        self.created_at = time.time()
    
    def is_expired(self) -> bool:
        """Verifica si la entrada expiró."""
        return (time.time() - self.created_at) > self.ttl


class CacheManager(Generic[T]):
    """
    Gestor de caché genérico, thread-safe, con TTL por clave.
    
    Responsabilidades:
    - Almacenar/recuperar valores (set/get)
    - Gestionar expiración per-clave
    - Orquestar refresh desde fetch_fn
    - Stats de hit/miss
    """
    
    def __init__(self, default_ttl: int = 30, name: str = "cache"):
        self._store: Dict[str, CacheEntry[T]] = {}
        self._default_ttl = default_ttl
        self._name = name
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "sets": 0}
    
    async def get(self, key: str) -> Optional[T]:
        """
        Obtiene valor del caché si existe y no expiró.
        
        Returns:
            Valor si existe y es válido, None si no existe o expiró
        """
        async with self._lock:
            if key not in self._store:
                self._stats["misses"] += 1
                return None
            
            entry = self._store[key]
            if entry.is_expired():
                del self._store[key]
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return entry.value
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Guarda un valor en caché.
        
        Args:
            key: clave
            value: valor a guardar
            ttl: TTL específico para esta clave (usa default_ttl si no especifica)
        """
        async with self._lock:
            ttl_to_use = ttl if ttl is not None else self._default_ttl
            self._store[key] = CacheEntry(value, ttl_to_use)
            self._stats["sets"] += 1
            logger.debug(f"{self._name}: set {key} (ttl={ttl_to_use}s)")
    
    async def get_or_fetch(
        self,
        key: str,
        fetch_fn,
        ttl: Optional[int] = None,
    ) -> Optional[T]:
        """
        Obtiene del caché o ejecuta fetch_fn si no existe/expiró.
        
        Args:
            key: clave
            fetch_fn: función async que retorna T
            ttl: TTL específico para resultado del fetch
        
        Returns:
            Valor (de caché o fetch_fn)
        """
        # Intentar obtener del caché primero
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # No estaba en caché, ejecutar fetch
        try:
            value = await fetch_fn()
            if value is not None:
                await self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.error(f"{self._name}: error fetching {key}: {e}")
            return None
    
    async def invalidate(self, key: str) -> None:
        """Invalida una clave específica."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug(f"{self._name}: invalidated {key}")
    
    async def clear(self) -> None:
        """Limpia todo el caché."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.debug(f"{self._name}: cleared {count} entries")
    
    async def cleanup_expired(self) -> int:
        """Limpia entradas expiradas. Retorna cantidad removida."""
        async with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired()]
            for k in expired_keys:
                del self._store[k]
            
            if expired_keys:
                logger.debug(f"{self._name}: cleaned {len(expired_keys)} expired entries")
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas."""
        return dict(self._stats)
    
    def reset_stats(self) -> None:
        """Reinicia estadísticas."""
        self._stats = {"hits": 0, "misses": 0, "sets": 0}
