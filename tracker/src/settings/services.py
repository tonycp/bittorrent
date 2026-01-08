from pydantic import BaseModel


class SocketSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5555


class NeighborSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5555


class ReplicationSettings(BaseModel):
    interval: int = 2  # segundos entre ciclos de replicación
    heartbeat_interval: int = 5  # segundos entre heartbeats
    timeout: float = 3.0  # timeout para requests de replicación
    max_retries: int = 2  # reintentos antes de marcar vecino como down


class CleanupSettings(BaseModel):
    interval: int = 300  # segundos entre ciclos de limpieza (5 min)
    peer_ttl_minutes: int = 30  # TTL de peers inactivos
    event_retention_minutes: int = 10  # retención de eventos tras replicar (10 min)


class ServiceSettings(BaseModel):
    tracker: SocketSettings = SocketSettings()
    tracker_id: str = "tracker-1"
    neighbors: list[NeighborSettings] = []
    replication: ReplicationSettings = ReplicationSettings()
    cleanup: CleanupSettings = CleanupSettings()
