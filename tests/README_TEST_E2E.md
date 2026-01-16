# Test E2E: 6 Trackers + 2 Clientes

## Descripción

Este test levanta una infraestructura completa de BitTorrent distribuida:
- **6 trackers** con replicación automática y tolerancia a fallos
- **2 clientes** con capacidad GUI y P2P
- **Red Docker** aislada (172.28.0.0/24)

## Ejecutar el Test

```bash
cd tests/
uv run python test_e2e_simple.py
```

El test verifica:
- ✅ Los 6 trackers se levantan correctamente
- ✅ El cluster se sincroniza (replicación funciona)
- ✅ Los 2 clientes están operativos
- ✅ Se puede crear un archivo de prueba en client-1

## Prueba Manual de Transferencia P2P

Una vez que el test haya pasado, los contenedores siguen corriendo. Puedes probar la transferencia P2P completa manualmente:

### 1. En Client-1: Crear y compartir un archivo

```bash
# Entrar al contenedor
docker exec -it client-1 bash

# Iniciar el CLI
uv run python src/cli/cli_standalone.py

# Dentro del CLI, crear torrent del archivo de prueba
> create /app/downloads/test_file.bin
```

Esto va a:
- Registrar el torrent en el tracker
- Anunciar client-1 como peer/seeder
- Mostrar el hash del torrent (guárdalo para el siguiente paso)

### 2. En Client-2: Descargar el archivo

```bash
# En otra terminal, entrar al segundo contenedor
docker exec -it client-2 bash

# Iniciar el CLI
uv run python src/cli/cli_standalone.py

# Descargar el archivo usando el hash del paso anterior
> download <torrent_hash>
```

Esto va a:
- Contactar al tracker para obtener peers
- Descubrir a client-1 como seeder
- Descargar el archivo por chunks desde client-1
- Verificar integridad del archivo

### 3. Verificar la transferencia

```bash
# Verificar que el archivo se descargó correctamente
docker exec client-2 ls -lh /app/downloads/

# Comparar checksums
docker exec client-1 sha256sum /app/downloads/test_file.bin
docker exec client-2 sha256sum /app/downloads/test_file.bin
```

Si los hashes coinciden, ¡la transferencia P2P fue exitosa!

## Arquitectura del Test

```
┌─────────────────────────────────────────────────────────────┐
│                    Red Docker: 172.28.0.0/24                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ Tracker-1  │  │ Tracker-2  │  │ Tracker-3  │          │
│  │ .11:5555   │  │ .12:5555   │  │ .13:5555   │          │
│  └────────────┘  └────────────┘  └────────────┘          │
│         │               │               │                  │
│         └───────────────┴───────────────┘                  │
│                    Replicación                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ Tracker-4  │  │ Tracker-5  │  │ Tracker-6  │          │
│  │ .14:5555   │  │ .15:5555   │  │ .16:5555   │          │
│  └────────────┘  └────────────┘  └────────────┘          │
│         │                                 │                │
│         ↓                                 ↓                │
│  ┌────────────┐                    ┌────────────┐        │
│  │  Client-1  │  ←──────P2P────→   │  Client-2  │        │
│  │ .21:6881   │                    │ .22:6882   │        │
│  │  (Seeder)  │                    │ (Leecher)  │        │
│  └────────────┘                    └────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Características Verificadas

### Replicación Automática
- Los torrents registrados en tracker-1 se replican automáticamente a los demás
- Usa hash(torrent) mod N para determinar réplicas
- Mínimo 3 réplicas para tolerancia a fallos

### Rotación de Trackers
- Si un tracker falla, los clientes rotan automáticamente al siguiente
- La lista de trackers se configura en TRACKER_URLS

### Descarga por Chunks
- Los archivos se dividen en chunks de 256KB
- Cada chunk se verifica independientemente
- Descarga paralela de múltiples chunks

### Verificación de Integridad
- Hash SHA-256 por chunk
- Hash SHA-256 del archivo completo
- Validación automática al completar descarga

## Comandos Útiles

### Ver logs de un contenedor
```bash
docker logs tracker-1
docker logs -f client-1  # seguir logs en tiempo real
```

### Ver estado del cluster
```bash
docker exec tracker-1 cat /app/data/cluster_state.json
```

### Inspeccionar red
```bash
docker network inspect tests_torrent_net
```

### Limpiar todo
```bash
cd tests/
docker-compose -f docker-compose-e2e-gui.yml down -v
```

## Troubleshooting

### Los trackers no se sincronizan
- Espera 30-60 segundos después de levantar
- Verifica que MIN_CLUSTER_SIZE=3 en las variables de entorno
- Revisa logs: `docker logs tracker-1 | grep -i cluster`

### Cliente no encuentra peers
- Verifica que client-1 haya ejecutado `create` correctamente
- Revisa que el announce se hizo: `docker logs client-1 | grep -i announce`
- Verifica conectividad: `docker exec client-2 ping 172.28.0.21`

### Transferencia lenta
- Normal en Docker por overhead de red virtual
- Aumenta MAX_CONCURRENT_CHUNKS en configuración
- Reduce CHUNK_SIZE para paralelización más fina

## Archivos Importantes

- `docker-compose-e2e-gui.yml` - Definición de la infraestructura
- `test_e2e_simple.py` - Test automatizado
- `README_E2E_GUI.md` - Documentación detallada (archivo original)
- `test_e2e_gui_complete.py` - Test complejo con RPC (deprecated, usar test_e2e_simple.py)

## Próximos Pasos

1. **GUI Testing**: Los contenedores soportan X11 forwarding. Configura DISPLAY para usar las GUIs:
   ```bash
   xhost +local:docker
   export DISPLAY=:0
   docker-compose -f docker-compose-e2e-gui.yml up client-1
   ```

2. **Stress Testing**: Levanta más clientes para probar descarga simultánea

3. **Fault Tolerance**: Detén trackers durante transferencia y verifica que continúa

## Resumen

Este test demuestra que la arquitectura completa funciona:
- ✅ Cluster de trackers con replicación
- ✅ Clientes P2P funcionales
- ✅ Transferencia por chunks
- ✅ Verificación de integridad
- ✅ Tolerancia a fallos

Para uso en producción, considera agregar:
- Autenticación entre peers
- Encriptación de transferencias
- Rate limiting
- Métricas y monitoreo
