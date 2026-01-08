# Arquitectura Distribuida del Tracker

Este documento describe la arquitectura distribuida del sistema de trackers y cómo difiere de la arquitectura centralizada original.

## Comparación: Centralizado vs Distribuido

### Arquitectura Centralizada (Original)

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Client  │───▶│ Tracker │◀───│ Client  │
└─────────┘     └─────────┘     └─────────┘
                      │
                 ┌────▼────┐
                 │   DB    │
                 └─────────┘
```

- **Punto único de fallo**: Si el tracker cae, todo el sistema se detiene
- **Escalabilidad limitada**: Un solo nodo maneja todas las peticiones
- **Sin replicación**: Estado en memoria/DB local sin respaldo

### Arquitectura Distribuida (Actual)

```
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Client  │───▶│Tracker-1 │◀─▶│Tracker-2 │◀─▶│Tracker-3 │
└─────────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
                     ▼               ▼│             ▼  │
                ┌─────────┐      ┌─────────┐     ┌─────────┐
                │  DB-1   │      │  DB-2   │     │  DB-3   │
                └─────────┘      └─────────┘     └─────────┘
                
        Replicación: Event Log + Vector Clocks
        Consistencia: Eventual con orden causal
```

- **Alta disponibilidad**: Sistema funciona con N-1 fallos (N trackers)
- **Escalabilidad horizontal**: Añadir trackers aumenta capacidad
- **Replicación automática**: Event log distribuido entre todos los nodos
- **Descubrimiento**: Cliente puede contactar cualquier tracker

## Componentes Clave

### 1. ent Sourcing

Todos los cambios de estado se modelan como eventos inmutables:

```python
class EventLog(Entity):
    tracker_id: str              # Tracker que generó el evento
    vector_clock: Dict[str, int] # Reloj vectorial para orden causal
    operation: str               # peer_announce | peer_stopped | peer_completed
    timestamp: int               # Versión local del tracker
    data: Data                   # Payload de la operación
```

**Ventajas:**

- Historial completo de cambios
- Reproducción de estado en cualquier punto
- Auditoría y debugging facilitados
- Base para replicación

### 2. Vector Clocks

Cada tracker mantiene un vector clock `{tracker_id: version}`:

```python
# Tracker-1 genera evento
vc = {"tracker-1": 5, "tracker-2": 3}

# Tracker-2 recibe y actualiza
vc_local = {"tracker-1": 4, "tracker-2": 4}
vc_merged = {
    "tracker-1": max(5, 4) = 5,
    "tracker-2": max(3, 4) + 1 = 5  # +1 por evento local
}
```

**Garantiza:**

- Orden causal entre eventos
- Detección de concurrencia
- Rechazo de eventos obsoletos

### 3. Servicios Background

#### ReplicationService

- **Loop de replicación**: cada 2s envía eventos pendientes a vecinos
- **Loop de heartbeat**: cada 5s confirma que vecinos están vivos
- **Estado por vecino**: `{last_ts, retries, alive}`

#### CleanupService

- **Peers inactivos**: elimina peers sin `last_announce` > 30 min
- **Torrents huérfanos**: elimina torrents sin peers
- **Event log**: purga eventos > 10 min tras replicar

### 4. Handlers Distribuidos

#### EventHandler

- `create_event`: Crea evento local, incrementa VC
- `apply_event`: Valida VC, aplica evento remoto
- `get_last_event`: Consulta último evento de un tracker

#### ReplicationHandler

- `replicate_events`: Aplica lote de eventos (idempotente)
- `heartbeat`: Confirma tracker vivo
- `request_snapshot`: Devuelve estado completo
- `replicate_snapshot`: Aplica snapshot inicial

## Flujos de Operación

### 1. Cliente Anuncia a Tracker-1

```
1. Client → Tracker-1: announce(peer_id, torrent_hash, ...)
2. Tracker-1: EventHandler.create_event("peer_announce", data)
3. Tracker-1: ReplicationHandler.peer_announce() → update DB
4. Tracker-1 (background): ReplicationService detecta evento pendiente
5. Tracker-1 → Tracker-2: replicate_events([event])
6. Tracker-2: EventHandler.apply_event() → valida VC
7. Tracker-2: ReplicationHandler.peer_announce() → update DB
8. Repetir para Tracker-3, ...
```

### 2. Cliente Consulta a Tracker-2

```
1. Client → Tracker-2: get_peers(torrent_hash)
2. Tracker-2: TrackerHandler.peer_list() → query DB local
3. Tracker-2 → Client: lista de peers (puede incluir info replicada de Tracker-1)
```

### 3. Tracker Nuevo se Une al Cluster

```
1. Tracker-3 arranca, configura neighbors=[Tracker-1, Tracker-2]
2. Tracker-3 → Tracker-1: request_snapshot()
3. Tracker-1 → Tracker-3: {torrents, peers, vc_actual}
4. Tracker-3: replicate_snapshot() → carga estado inicial
5. Tracker-3 entra en modo replicación incremental desde vc_actual
```

### 4. Tracker-1 Cae

```
1. Tracker-2 y Tracker-3 detectan fallo (heartbeat timeout)
2. Marcan Tracker-1 como "down", dejan de intentar replicar
3. Clientes redirigen a Tracker-2 o Tracker-3
4. Sistema sigue operando con 2/3 trackers
5. Tracker-1 se recupera → recibe heartbeat → reactivado
6. Tracker-1 solicita eventos pendientes o snapshot
```

## Garantías y Limitaciones

### Garantías

✅ **Consistencia eventual**: Todos los trackers convergen al mismo estado  
✅ **Orden causal**: Eventos relacionados se aplican en orden correcto  
✅ **Idempotencia**: Reintentos no causan duplicados  
✅ **Tolerancia a fallos**: Sistema sobrevive a (N-1)/2 fallos  
✅ **Escalabilidad**: Añadir trackers aumenta capacidad

### Limitaciones

⚠️ **Latencia de replicación**: Cambios visibles tras 2-5s (configurable)  
⚠️ **Eventos concurrentes**: Resolución por "último escritor gana"  
⚠️ **Sin consenso fuerte**: No hay garantía de linearizabilidad  
⚠️ **Particiones de red**: Posible split-brain (sin quorum automático)  
⚠️ **Crecimiento del log**: Requiere purga periódica (implementada)

## Configuración de Producción

### Cluster de 3 Trackers (Tolerancia a 1 Fallo)

```yaml
# Tracker-1 (192.168.1.10:5560)
services:
  tracker_id: "tracker-1"
  tracker:
    host: "0.0.0.0"
    port: 5560
  neighbors:
    - host: "192.168.1.11"
      port: 5561
    - host: "192.168.1.12"
      port: 5562

# Tracker-2 (192.168.1.11:5561)
services:
  tracker_id: "tracker-2"
  tracker:
    host: "0.0.0.0"
    port: 5561
  neighbors:
    - host: "192.168.1.10"
      port: 5560
    - host: "192.168.1.12"
      port: 5562

# Tracker-3 (192.168.1.12:5562)
services:
  tracker_id: "tracker-3"
  tracker:
    host: "0.0.0.0"
    port: 5562
  neighbors:
    - host: "192.168.1.10"
      port: 5560
    - host: "192.168.1.11"
      port: 5561
```

### Cluster de 5 Trackers (Tolerancia a 2 Fallos)

Similar al anterior, añadiendo:

```yaml
# Tracker-4 y Tracker-5 con puertos 5563, 5564
# Cada uno lista a los otros 4 en neighbors
```

## Monitoreo y Debugging

### Logs Relevantes

```bash
# Replicación exitosa
INFO - Replicated 10 events to 192.168.1.11:5561

# Fallo de replicación
WARNING - Failed to replicate to 192.168.1.11:5561: timeout
ERROR - Neighbor 192.168.1.11:5561 marked as down after 2 retries

# Cleanup
INFO - Removed 5 inactive peers
INFO - Purged 150 old events

# Heartbeat
INFO - Neighbor 192.168.1.11:5561 is alive again
```

### Métricas Clave

- **Eventos pendientes por vecino**: `last_ts` vs timestamp actual
- **Vecinos activos**: número de `alive=True`
- **Latencia de replicación**: tiempo entre evento local y aplicación remota
- **Tasa de cleanup**: peers/events eliminados por ciclo

## Trabajo Futuro

### Discovery Automático

- Broadcast/multicast en subred local
- Registro de trackers en servicio central (ej. etcd, Consul)
- DNS SRV records para resolución

### Mejoras de Consistencia

- Quorum para escrituras críticas
- Leader election para coordinación
- Conflict-free Replicated Data Types (CRDTs)

### Optimizaciones

- Compresión de event log (snapshots periódicos)
- Replicación selectiva (solo torrents activos)
- Particionamiento por hash de torrent_hash
