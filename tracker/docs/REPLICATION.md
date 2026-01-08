# Protocolo de Replicación entre Trackers

Este documento describe el protocolo de replicación distribuida implementado en el sistema de trackers.

## Modelo de Datos

### Event Log

Todos los cambios de estado (announce, stop, completed) se registran como eventos con:

- `tracker_id`: Identificador del tracker que generó el evento
- `vector_clock`: Reloj vectorial para ordenamiento causal (`{tracker_id: version}`)
- `operation`: Tipo de operación (`peer_announce`, `peer_stopped`, `peer_completed`)
- `timestamp`: Timestamp local del evento (versión del tracker emisor)
- `data`: Payload específico de la operación

### Vector Clocks

Cada tracker mantiene un vector clock que se incrementa en cada operación local y se actualiza (merge + max) al recibir eventos remotos. Esto permite:

- Detectar orden causal entre eventos
- Identificar eventos concurrentes
- Rechazar eventos que violan causalidad

## Endpoints de Replicación

### `Replication:update:replicate_events`

Recibe un lote de eventos de otro tracker.

**Request:**
```json
{
  "controller": "Replication",
  "command": "update",
  "func": "replicate_events",
  "data": {
    "source_tracker_id": "tracker-1",
    "events": [
      {
        "tracker_id": "tracker-1",
        "vector_clock": {"tracker-1": 5, "tracker-2": 3},
        "operation": "peer_announce",
        "timestamp": 5,
        "data": {
          "peer_id": "peer123",
          "torrent_hash": "abc...",
          "ip": "192.168.1.10",
          "port": 6881,
          ...
        }
      }
    ]
  }
}
```

**Response:**
```json
{
  "status": "ok",
  "applied": 10,
  "errors": [],
  "source_tracker": "tracker-1"
}
```

### `Replication:create:heartbeat`

Confirma que un tracker está vivo y comunica su estado.

**Request:**
```json
{
  "controller": "Replication",
  "command": "create",
  "func": "heartbeat",
  "data": {
    "tracker_id": "tracker-1",
    "last_timestamp": 42,
    "event_count": 0
  }
}
```

**Response:**
```json
{
  "status": "alive",
  "tracker_id": "tracker-2",
  "acknowledged_timestamp": 42
}
```

### `Replication:get:request_snapshot`

Solicita un snapshot completo del estado actual (para tracker nuevo).

**Request:**
```json
{
  "controller": "Replication",
  "command": "get",
  "func": "request_snapshot",
  "data": {
    "tracker_id": "tracker-3"
  }
}
```

**Response:**
```json
{
  "source_tracker_id": "tracker-1",
  "vector_clock": {"tracker-1": 100, "tracker-2": 95},
  "torrents": [...],
  "peers": [...]
}
```

### `Replication:update:replicate_snapshot`

Aplica un snapshot inicial recibido de otro tracker.

**Request:**
```json
{
  "controller": "Replication",
  "command": "update",
  "func": "replicate_snapshot",
  "data": {
    "source_tracker_id": "tracker-1",
    "vector_clock": {"tracker-1": 100},
    "torrents": [...],
    "peers": [...]
  }
}
```

**Response:**
```json
{
  "status": "snapshot_applied",
  "source_tracker": "tracker-1",
  "torrents_count": 50,
  "peers_count": 200,
  "vector_clock": {"tracker-1": 100}
}
```

## Flujos de Replicación

### Replicación Incremental (Normal)

1. Cada Δt (2s por defecto), tracker ejecuta loop de replicación
2. Para cada vecino, consulta `EventLogRepository.get_pending_replication(last_ts)`
3. Envía lote de eventos vía `replicate_events`
4. Vecino valida orden causal con `EventHandler.apply_event`
5. Si válido, aplica vía `ReplicationHandler` (idempotente)
6. Tracker emisor actualiza `last_ts` del vecino
7. En caso de fallo, incrementa contador de reintentos; tras N fallos marca vecino como `down`

### Heartbeat

1. Cada Δt (5s por defecto), tracker envía `heartbeat` a vecinos
2. Vecino responde confirmando que está vivo
3. Si vecino estaba marcado `down` y responde, se reactiva

### Snapshot Inicial (Tracker Nuevo)

1. Tracker nuevo se une al cluster
2. Solicita `request_snapshot` a un vecino conocido
3. Vecino responde con estado completo (torrents, peers, VC actual)
4. Tracker nuevo aplica snapshot vía `replicate_snapshot`
5. A partir de ahí, recibe eventos incrementales desde ese VC

## Consistencia y Resolución de Conflictos

### Validación Causal

Al recibir evento remoto, `EventHandler._should_apply` compara VCs:

```python
def _should_apply(local_vc, remote_vc):
    # Remoto debe ser estrictamente mayor o igual en todas las dimensiones
    # y estrictamente mayor en al menos una
    all_keys = set(local_vc) | set(remote_vc)
    less_or_equal = all(local_vc[k] <= remote_vc[k] for k in all_keys)
    strictly_less = any(local_vc[k] < remote_vc[k] for k in all_keys)
    return less_or_equal and strictly_less
```

Si falla, evento se rechaza con `ServiceError`.

### Idempotencia

Todos los métodos de `ReplicationHandler` son idempotentes:

- `peer_announce`: Upsert en `PeerRepository` (sobrescribe si existe)
- `peer_stopped`: Remove peer de torrent (no-op si no existe)
- `peer_completed`: Marca `is_seed=True` (idempotente)

Esto permite reintentos seguros sin duplicados.

### Eventos Concurrentes

Si dos trackers generan eventos concurrentes (VCs no ordenados), se aceptan ambos y se resuelven a nivel de aplicación:

- `peer_announce`: Último escritor gana (basado en timestamp o versión mayor)
- `peer_stopped`: Eliminación prevalece sobre actualización
- `peer_completed`: Estado de seeder se mantiene (idempotente)

## Configuración

### Settings (`tracker/src/settings/services.py`)

```python
class ServiceSettings(BaseModel):
    tracker_id: str = "tracker-1"
    neighbors: list[NeighborSettings] = []
    replication: ReplicationSettings = ReplicationSettings(
        interval=2,              # Ciclo de replicación (segundos)
        heartbeat_interval=5,    # Ciclo de heartbeat (segundos)
        timeout=3.0,             # Timeout para requests
        max_retries=2            # Reintentos antes de marcar down
    )
```

### Neighbors

Lista de vecinos con `host` y `port`:

```python
neighbors = [
    NeighborSettings(host="192.168.1.10", port=5561),
    NeighborSettings(host="192.168.1.11", port=5562),
]
```

## Limpieza y Mantenimiento

### Cleanup de Peers Inactivos

- Frecuencia: cada 5 minutos
- TTL: 30 minutos sin `last_announce`
- Elimina peers + torrents huérfanos

### Purga de Event Log

- Frecuencia: cada 5 minutos
- Retención: 10 minutos tras replicación
- Evita crecimiento indefinido de la tabla `events`

## Tolerancia a Fallos

- **N trackers**: Toleran (N-1)/2 fallos simultáneos
- **Mínimo 3 trackers**: Tolerancia a 1 fallo
- **Recomendado 5 trackers**: Tolerancia a 2 fallos
- Si tracker cae: vecinos dejan de replicarle; al volver, recibe eventos pendientes o snapshot
- Si mayoría cae: sistema sigue funcionando con trackers sobrevivientes (eventual consistency al recuperarse)
