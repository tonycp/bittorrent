# Cliente BitTorrent - Arquitectura Simplificada

## Descripción General

Cliente BitTorrent moderno que utiliza `bit_lib` para toda la comunicación con trackers. El cliente se enfoca en la interfaz de usuario (CLI y GUI) y la coordinación con trackers, delegando toda la lógica de red y protocolo a `bit_lib`.

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Capa de UI                           │
│  ┌──────────────┐              ┌──────────────┐        │
│  │   GUI (Tk)   │              │     CLI      │        │
│  └──────┬───────┘              └──────┬───────┘        │
│         │                             │                 │
│         └──────────────┬──────────────┘                 │
└────────────────────────┼──────────────────────────────┘
                         │
┌────────────────────────┼──────────────────────────────┐
│              Capa de Adaptadores                       │
│                ┌──────▼───────┐                        │
│                │TorrentClient │  (Adapter)             │
│                └──────┬───────┘                        │
└───────────────────────┼────────────────────────────────┘
                        │
┌───────────────────────┼────────────────────────────────┐
│           Capa de Coordinación                         │
│                ┌──────▼──────┐                         │
│                │ClientManager│                         │
│                └──────┬──────┘                         │
│                       │                                 │
│                ┌──────▼──────┐                         │
│                │TrackerMngr  │                         │
│                └──────┬──────┘                         │
└───────────────────────┼────────────────────────────────┘
                        │
┌───────────────────────┼────────────────────────────────┐
│          Capa de Comunicación (bit_lib)                │
│                ┌──────▼──────┐                         │
│                │TrackerClient│ (bit_lib.services)      │
│                └──────┬──────┘                         │
│                       │                                 │
│          ┌────────────▼───────────┐                    │
│          │ ClientService (bit_lib)│                    │
│          │  - Request/Response    │                    │
│          │  - Socket Management   │                    │
│          │  - Async I/O           │                    │
│          └────────────┬───────────┘                    │
└───────────────────────┼────────────────────────────────┘
                        │
                        ▼
              ┌──────────────┐
              │   Trackers   │
              │  (Register)  │
              │    (Bit)     │
              └──────────────┘
```

## Componentes

### 1. **TorrentClient** (Adaptador)
- **Ubicación**: `client/core/torrent_client.py`
- **Responsabilidad**: Adaptar la interfaz de la GUI a ClientManager
- **Características**:
  - Mantiene compatibilidad con GUI existente
  - Gestiona ciclo de vida de la sesión
  - Carga información de archivos `.p2p`

### 2. **ClientManager** (Coordinador)
- **Ubicación**: `client/core/client_manager.py`
- **Responsabilidad**: Coordinar comunicación con trackers
- **Características**:
  - Event loop asíncrono en thread separado (para GUI responsiva)
  - Gestiona torrents registrados
  - Coordina TrackerManager
  - **Simplificado**: Ya no gestiona PeerService ni NetworkManager

### 3. **TrackerManager** (Manager de Trackers)
- **Ubicación**: `client/core/tracker_manager.py`
- **Responsabilidad**: Comunicación con trackers usando bit_lib
- **Características**:
  - Registro de torrents
  - Announce de peers
  - Obtención de lista de peers
  - Tolerancia a fallos (failover entre trackers)
  - **Simplificado**: Ya no depende de NetworkManager

### 4. **TrackerClient** (Cliente bit_lib)
- **Ubicación**: `client/connection/tracker_client.py`
- **Responsabilidad**: Cliente asíncrono que extiende bit_lib.services.ClientService
- **Características**:
  - Usa Request/Response models de bit_lib
  - Comunicación con controllers: `Register`, `Bit`
  - Métodos:
    - `register_torrent()`: Register:create:create_torrent
    - `announce_peer()`: Bit:create:announce
    - `stop_announce()`: Bit:create:announce (event="stopped")
    - `get_peers()`: Bit:get:peer_list

## Endpoints del Tracker

### Registro de Torrent
```python
Request(
    controller="Register",
    command="create",
    func="create_torrent",
    args={
        "info_hash": str,
        "file_name": str,
        "file_size": int,
        "chunk_size": int,
        "peer_id": str,
        "piece_length": int  # ⚠️ Requerido
    }
)
```

### Announce
```python
Request(
    controller="Bit",
    command="create",
    func="announce",
    args={
        "info_hash": str,
        "peer_id": str,
        "ip": str,
        "port": int,
        "left": int,  # bytes restantes
        "event": str | None  # "started" | "stopped" | None
    }
)
```

### Obtener Peers
```python
Request(
    controller="Bit",
    command="get",
    func="peer_list",
    args={
        "info_hash": str
    }
)
# Response: data.data.peers = [{"peer_id", "ip", "port"}, ...]
```

## Cambios Principales (Simplificación)

### ❌ Removido (código viejo que duplicaba bit_lib):
- `client/connection/network.py` - Socket management viejo
- `client/connection/peer_conn.py` - Conexiones P2P viejas
- `client/connection/protocol.py` - Protocolo viejo
- `client/services/peer_service.py` - Servicio P2P viejo
- `NetworkManager` dependency en ClientManager y TrackerManager
- `PeerService` initialization en ClientManager

### ✅ Mantenido (funcionalidad core):
- `TrackerClient` (extiende bit_lib.services.ClientService)
- `TrackerManager` (coordinación de trackers)
- `ClientManager` (coordinación general simplificada)
- `TorrentClient` (adaptador para GUI)
- GUI (Tkinter)
- CLI

### 🔧 Modificado:
- **ClientManager**: Ya no acepta `network` parameter, solo `config_manager`
- **TrackerManager**: Ya no acepta `network` parameter, obtiene IP directamente con `socket.gethostname()`
- **TorrentClient**: Ya no crea `NetworkManager`, solo `ClientManager`

## Flujo de Registro de Torrent

```
1. GUI/CLI llama TorrentClient.add_torrent(torrent_info)
2. TorrentClient llama ClientManager.add_torrent(...)
3. ClientManager llama TrackerManager.register_torrent_async(...)
4. TrackerManager llama TrackerClient.register_torrent(...)
5. TrackerClient crea Request(controller="Register", command="create", ...)
6. ClientService (bit_lib) envía request al tracker
7. Tracker responde con Response(status="ok", ...)
8. Se propaga success/error hasta GUI
```

## Configuración

### Configuración del Cliente
- **Archivo**: `client.conf`
- **Secciones**:
  - `[Tracker]`: Configuración del tracker principal
  - `[General]`: Paths, listen_port, etc.
  - `[UI]`: Configuración de interfaz

### Variables de Entorno
- `MIN_CLUSTER_SIZE`: Tamaño mínimo del cluster de trackers (default: 3)
- `ENVIRONMENT`: `development` | `production`

## Testing

### Test Básico de Tracker
```bash
cd client
uv run test_client_basic.py
```

Tests:
1. ✅ Registro de torrent
2. ✅ Announce de peer
3. ✅ Obtención de lista de peers

### Test de Imports de GUI
```bash
cd client
uv run test_gui_imports.py
```

Valida:
1. ✅ ConfigManager importable
2. ✅ TorrentClient creatable
3. ✅ Sesión inicializable
4. ✅ TrackerClient importable
5. ⚠️ GUI importable (requiere tkinter system lib)

## Ejecución

### CLI
```bash
cd client
uv run cli_main.py
```

### GUI (requiere display)
```bash
cd client
uv run -m client.gui.client
```

### CLI Simple (directo)
```bash
cd client
python cli_simple.py
```

## Dependencias

### Runtime
- **bit_lib**: Comunicación con trackers
- aiohttp: Cliente HTTP async
- tkinter: GUI (requiere `python3-tk` system package)

### Development
- debugpy: Debugging remoto
- docker: Docker SDK para Python

## Notas

### ⚠️ Estado Actual
- ✅ Comunicación con tracker funcionando completamente
- ✅ Registro, announce, get_peers validados
- ⚠️ **Transferencia de chunks P2P**: No implementada en esta versión simplificada
- 🎯 **Enfoque**: UI + comunicación con tracker solamente

### 🔮 Futuro
Para transferencia P2P completa, se podría:
1. Usar `bit_lib.services.PeerService` para hosting de chunks
2. Implementar `FileDownloader` usando bit_lib para descargas
3. O mantener transferencia P2P como componente separado

### 🏗️ Arquitectura Limpia
Esta simplificación logra:
- ✅ Separación clara de responsabilidades
- ✅ Código más mantenible (menos duplicación)
- ✅ Tests más simples y confiables
- ✅ Menor superficie de errores
- ✅ Facilita futura integración completa con bit_lib
