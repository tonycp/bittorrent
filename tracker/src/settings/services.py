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


class ClusterSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5556  # Puerto dedicado para comunicación cluster
    sync_interval: int = 10  # segundos entre ciclos de discovery
    heartbeat_interval: int = 5  # segundos entre heartbeats
    liveness_timeout: int = 15  # segundos sin respuesta para marcar ausente
    purge_timeout: int = 60  # segundos para eliminar definitivamente
    cleanup_interval: int = 60  # segundos entre normalizaciones (solo líder)
    service_name: str = "tracker"  # Nombre del servicio Docker para discovery
    heartbeat_fail_threshold: int = 2  # Fallos consecutivos para disparar elección
    election_semaphore_size: int = 10  # Concurrencia máxima en consultas de elección
    discovery_timeout: float = 2.0  # Timeout para ping-sweep en discovery
    discovery_ping_subnet: str = "172.17.0.0/16"  # Subnet para ping-sweep fallback
    discovery_ping_max_workers: int = 10  # Workers máximos para ping-sweep
    rpc_timeout: float = 5.0  # Timeout para requests RPC
    min_cluster_size: int = 1  # Mínimo de trackers para considerar cluster estable


class ServiceSettings(BaseModel):
    tracker: SocketSettings = SocketSettings()
    tracker_id: str = "tracker-1"
    neighbors: list[NeighborSettings] = []
    replication: ReplicationSettings = ReplicationSettings()
    cleanup: CleanupSettings = CleanupSettings()
    cluster: ClusterSettings = ClusterSettings()
