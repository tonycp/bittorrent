# Cliente BitTorrent

Cliente P2P para el sistema BitTorrent distribuido. Soporta dos interfaces:

- **GUI**: Interfaz gráfica con Tkinter (escritorio)
- **CLI**: Interfaz de línea de comandos (servidores, contenedores)

## Características

- 🔄 Descarga/upload P2P de chunks en paralelo
- 🌐 Comunicación con trackers replicados (tolerancia a fallos)
- 📊 Monitoreo de progreso en tiempo real
- 🐳 Compatible con Docker
- ⚡ Arquitectura asíncrona basada en `bit_lib`
- 🔧 Configuración flexible

## Instalación

### Con uv (recomendado)

```bash
cd client
uv sync
```

### Con pip

```bash
cd client
pip install -e .
```

## Uso

### GUI (Interfaz Gráfica)

```bash
python main.py
```

Abre una ventana Tkinter con:
- Lista de torrents activos
- Barra de progreso por torrent
- Botones para añadir/pausar/reanudar/eliminar
- Configuración de tracker y carpetas

### CLI (Línea de Comandos)

```bash
python cli_main.py
```

Abre un shell interactivo:

```
bittorrent> add ubuntu.p2p
bittorrent> list
bittorrent> watch
bittorrent> help
```

**Ver guía completa**: [CLI_USAGE.md](CLI_USAGE.md)

## Comandos CLI Principales

```bash
# Gestión de torrents
add <archivo.p2p>     # Añadir torrent
list / ls             # Listar torrents
info <handle>         # Ver detalles
pause <handle>        # Pausar descarga
resume <handle>       # Reanudar descarga
remove <handle>       # Eliminar torrent

# Monitoreo
watch [handle]        # Monitorear progreso en tiempo real

# Configuración
config                # Ver configuración
config set <k> <v>    # Modificar configuración
restart               # Reiniciar cliente

# Debug
connect <host> <port> # Conectar a peer manualmente
debug                 # Ver información de debug

# Sistema
clear / cls           # Limpiar pantalla
exit / quit / q       # Salir
```

## Arquitectura

### Componentes Principales

```
┌─────────────────────┐
│   GUI / CLI         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   TorrentClient     │ (Adaptador)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   ClientManager     │ (Coordinador)
│  - Event Loop       │
│  - Download Logic   │
└──┬───────────────┬──┘
   │               │
   ▼               ▼
┌──────────┐  ┌──────────────┐
│PeerService│  │TrackerManager│
│(P2P)      │  │(Tracker comms)│
└──────────┘  └──────────────┘
```

### PeerService
- Servidor: Escucha peticiones de chunks
- Cliente: Solicita chunks a otros peers
- Transferencia binaria eficiente
- Upload/download concurrente

### TrackerManager
- Comunicación con múltiples trackers
- Tolerancia a fallos (rotación automática)
- Announce periódico
- Descubrimiento de peers

### ClientManager
- Event loop asíncrono en thread separado
- Descarga de hasta 5 chunks en paralelo por torrent
- Gestión de múltiples torrents simultáneos
- API síncrona para GUI/CLI

## Configuración

Archivo: `~/.config/bittorrent/config.ini`

```ini
[General]
download_path = /home/user/downloads
torrent_path = /home/user/torrents
listen_port = 6881
tracker_address = tracker:5555
max_download_rate = 0
max_upload_rate = 0
```

## Docker

### GUI (requiere X11)

```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $HOME/downloads:/downloads \
  bittorrent-client
```

### CLI (sin GUI)

```bash
docker run -it --rm \
  -v $HOME/downloads:/downloads \
  bittorrent-client \
  python cli_main.py
```

### Docker Compose

```yaml
services:
  client:
    build: ./client
    volumes:
      - ./downloads:/downloads
      - ./torrents:/torrents
    environment:
      - TRACKER_HOST=tracker
      - TRACKER_PORT=5555
      - LISTEN_PORT=6881
    ports:
      - "6881:6881"
    networks:
      - torrent_net
```

## Ejemplo de Uso Completo

### GUI

1. Iniciar GUI: `python main.py`
2. Configurar tracker en `Herramientas > Configuración`
3. Añadir torrent: `Archivo > Abrir Torrent`
4. Monitorear progreso en la tabla
5. Archivo descargado aparece en carpeta de descargas

### CLI

```bash
$ python cli_main.py

bittorrent> config set tracker_host tracker.example.com
bittorrent> config set download_path /mnt/storage
bittorrent> restart

bittorrent> add ubuntu.p2p
✓ Torrent añadido: ubuntu-22.04.iso

bittorrent> watch
# Monitorear progreso...

bittorrent> exit
```

## Testing

### Probar con múltiples clientes

```bash
# Terminal 1: Seed (cliente con archivo completo)
python cli_main.py
bittorrent> add complete_file.p2p

# Terminal 2: Leecher 1
python cli_main.py
bittorrent> config set listen_port 6882
bittorrent> restart
bittorrent> add complete_file.p2p

# Terminal 3: Leecher 2
python cli_main.py
bittorrent> config set listen_port 6883
bittorrent> restart
bittorrent> add complete_file.p2p
```

## Troubleshooting

### Puerto en uso
```bash
# Cambiar puerto de escucha
bittorrent> config set listen_port 6882
bittorrent> restart
```

### Tracker no disponible
```bash
# El cliente rotará automáticamente entre trackers conocidos
# Ver estado:
bittorrent> debug
```

### Descarga lenta
```bash
# Ver peers disponibles:
bittorrent> info <handle>

# Verificar que hay peers activos
# Si no hay peers, verificar tracker
```

## Logs

- GUI: `client.log`
- CLI: `bittorrent_cli.log`

```bash
tail -f bittorrent_cli.log
```

## Documentación Adicional

- [Arquitectura Completa](README_NEW_ARCHITECTURE.md)
- [Guía de CLI](CLI_USAGE.md)
- [Protocolo de Comunicación](../bit_lib/docs/PROTOCOL.md)

## Comparación GUI vs CLI

| Característica | GUI | CLI |
|----------------|-----|-----|
| Interfaz gráfica | ✓ | ✗ |
| Todas las operaciones | ✓ | ✓ |
| Monitoreo tiempo real | ✓ | ✓ |
| Uso en Docker | Limitado | ✓ |
| Automatización | ✗ | ✓ |
| Recursos | Alto | Bajo |
| SSH remoto | Difícil | ✓ |

## Contribuir

Ver estructura del proyecto:
```
client/
├── client/
│   ├── cli/              # CLI interactivo
│   ├── config/           # Gestión de configuración
│   ├── connection/       # TrackerClient, NetworkManager
│   ├── core/             # ClientManager, TorrentClient
│   ├── gui/              # GUI Tkinter
│   └── services/         # PeerService
├── cli_main.py           # Entry point CLI
├── main.py               # Entry point GUI
└── pyproject.toml
```

## Licencia

MIT
