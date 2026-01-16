# 🧪 Guía Completa de Testing - Sistema BitTorrent P2P

## 📋 Índice
1. [Comandos Docker Básicos](#comandos-docker-básicos)
2. [Monitoreo de Trackers](#monitoreo-de-trackers)
3. [Monitoreo de Clientes](#monitoreo-de-clientes)
4. [Testing de Funcionalidades](#testing-de-funcionalidades)
5. [Logs por Componente](#logs-por-componente)
6. [Scripts de Testing Automatizados](#scripts-de-testing-automatizados)

---

## 🐳 Comandos Docker Básicos

### Levantar el Sistema
```bash
cd /home/daaku/Projects/Escuela/bittorrent/tests

# Levantar todo (4 trackers + 3 clientes)
docker compose -f docker-compose-4trackers.yml up -d

# Ver el estado de los contenedores
docker compose -f docker-compose-4trackers.yml ps

# Ver logs en tiempo real de todos los servicios
docker compose -f docker-compose-4trackers.yml logs -f
```

### Controlar Servicios Individuales
```bash
# Reiniciar un servicio específico
docker compose -f docker-compose-4trackers.yml restart tracker-1
docker compose -f docker-compose-4trackers.yml restart client-1

# Detener un servicio
docker compose -f docker-compose-4trackers.yml stop tracker-2

# Levantar un servicio detenido
docker compose -f docker-compose-4trackers.yml start tracker-2

# Bajar todo el sistema
docker compose -f docker-compose-4trackers.yml down

# Bajar y eliminar volúmenes
docker compose -f docker-compose-4trackers.yml down -v
```

### Inspeccionar Contenedores
```bash
# Ver IPs asignadas
docker inspect tracker-1 | grep IPAddress
docker inspect client-1 | grep IPAddress

# Ver variables de entorno
docker exec tracker-1 env | grep SERVICES

# Ver procesos corriendo
docker exec tracker-1 sh -c "ps aux"
```

---

## 🎯 Monitoreo de Trackers

### Logs Generales de Trackers
```bash
# Ver logs de todos los trackers
docker logs tracker-1 --tail 100 -f
docker logs tracker-2 --tail 100 -f
docker logs tracker-3 --tail 100 -f
docker logs tracker-4 --tail 100 -f

# Ver logs de los últimos 2 minutos
docker logs tracker-1 --since 2m

# Buscar errores en todos los trackers
for i in 1 2 3 4; do
  echo "=== TRACKER-$i ==="
  docker logs tracker-$i 2>&1 | grep -i error | tail -10
done
```

### Logs de Cluster y Replicación
```bash
# Ver logs de descubrimiento de peers (cluster)
docker logs tracker-1 2>&1 | grep -E "Discovery|DNS|Ping sweep" | tail -20

# Ver logs de sincronización de cluster
docker logs tracker-1 2>&1 | grep -E "sync|cluster_sync" | tail -30

# Ver logs de elección de coordinador (Bully algorithm)
docker logs tracker-1 2>&1 | grep -E "coordinator|election|Bully" | tail -20

# Ver logs de replicación de eventos
docker logs tracker-1 2>&1 | grep -E "replication|event|apply_event" | tail -30

# Ver heartbeat entre trackers
docker logs tracker-1 2>&1 | grep -E "heartbeat|alive" | tail -20
```

### Logs de Operaciones de Tracker
```bash
# Ver announces de peers
docker logs tracker-1 2>&1 | grep -E "announce|peer_list" | tail -30

# Ver registros de torrents
docker logs tracker-1 2>&1 | grep -E "create_torrent|register|file_info" | tail -20

# Ver operaciones de scrape
docker logs tracker-1 2>&1 | grep -E "scrape|statistics" | tail -20

# Ver limpieza de peers inactivos
docker logs tracker-1 2>&1 | grep -E "cleanup|inactive|removed" | tail 20
```

### Logs de Vector Clock (Orden Causal)
```bash
# Ver operaciones del vector clock
docker logs tracker-1 2>&1 | grep -E "VectorClock|causal|concurrent" | tail -20
```

### Estado del Cluster en Tiempo Real
```bash
# Ver todos los logs relacionados con cluster
docker logs tracker-1 -f 2>&1 | grep -E "cluster|sync|coordinator|peer.*discovered"

# Ver solo mensajes INFO de cluster
docker logs tracker-1 -f 2>&1 | grep -E "INFO.*cluster"
```

---

## 💻 Monitoreo de Clientes

### Logs Generales de Clientes
```bash
# Ver logs de un cliente específico
docker logs client-1 --tail 100 -f
docker logs client-2 --tail 100 -f
docker logs client-3 --tail 100 -f

# Ver logs de los últimos 5 minutos
docker logs client-1 --since 5m

# Buscar errores
docker logs client-1 2>&1 | grep -i error | tail -20
```

### Logs de TrackerManager y Discovery
```bash
# Ver inicio del TrackerManager
docker logs client-1 2>&1 | grep "TrackerManager" | tail -20

# Ver discovery de trackers
docker logs client-1 2>&1 | grep -E "Discovery|DNS discovery|Ping sweep" | tail -30

# Ver trackers añadidos
docker logs client-1 2>&1 | grep "Tracker añadido" | tail -20

# Ver tracker actual conectado
docker logs client-1 2>&1 | grep -E "tracker principal|current tracker" | tail -10
```

### Logs de Descargas P2P
```bash
# Ver progreso de descarga
docker logs client-1 2>&1 | grep -E "DOWNLOAD.*Chunk.*descargado|progress" | tail -40

# Ver de qué peers se están descargando chunks
docker logs client-1 2>&1 | grep "Descargando chunk.*de" | tail -30

# Ver announces durante descarga
docker logs client-1 2>&1 | grep "Anunciando progreso" | tail -20

# Ver cuando se completa una descarga
docker logs client-1 2>&1 | grep -E "Descarga completa|100\.0%" | tail -10
```

### Logs de PeerService (Servidor P2P)
```bash
# Ver archivos registrados para seeding
docker logs client-1 2>&1 | grep "registrado para seeding" | tail -20

# Ver requests de chunks recibidos
docker logs client-1 2>&1 | grep "Sirviendo chunk" | tail -30

# Ver conexiones de peers
docker logs client-1 2>&1 | grep -E "Peer conectado|Peer desconectado" | tail -20
```

### Logs de GUI
```bash
# Ver actualizaciones de la GUI
docker logs client-1 2>&1 | grep "GUI_UPDATE" | tail -30

# Ver estado de torrents
docker logs client-1 2>&1 | grep -E "GET_STATUS|Torrent:" | tail -40
```

### Logs de Comunicación con Tracker
```bash
# Ver operaciones de registro de torrents
docker logs client-1 2>&1 | grep "registrado en" | tail -20

# Ver obtención de peers
docker logs client-1 2>&1 | grep "Obtenidos.*peers" | tail -20

# Ver announces exitosos
docker logs client-1 2>&1 | grep "Announce exitoso" | tail -20
```

---

## 🧪 Testing de Funcionalidades

### 1. Test de Discovery de Trackers

```bash
# Reiniciar cliente y ver discovery inicial
docker restart client-1 && sleep 8
docker logs client-1 2>&1 | grep -E "Discovery|Tracker añadido" | tail -20

# Verificar trackers descubiertos (debería encontrar 4)
docker logs client-1 2>&1 | grep "Discovery encontró" | tail -5
```

### 2. Test de Creación de Torrent

```bash
# Crear archivo de prueba en client-1
docker exec client-1 bash -c 'dd if=/dev/urandom of=/app/downloads/test_file.bin bs=1M count=2 2>/dev/null && ls -lh /app/downloads/test_file.bin'

# Verificar que el archivo se creó
docker exec client-1 ls -lh /app/downloads/

# Ver logs de creación de torrent (si se hace desde GUI)
docker logs client-1 2>&1 | grep -E "create_torrent|Torrent.*registrado" | tail -10
```

### 3. Test de Descarga P2P entre 3 Clientes

```bash
# Paso 1: Crear archivo en client-1
docker exec client-1 bash -c 'dd if=/dev/urandom of=/app/downloads/test_p2p.bin bs=1M count=3 2>/dev/null'

# Paso 2: Esperar a que se cree el torrent y se registre
sleep 5

# Paso 3: Ver progreso de descarga en client-2
docker logs client-2 -f 2>&1 | grep -E "DOWNLOAD.*Chunk|progress"

# Paso 4: Ver progreso en client-3
docker logs client-3 -f 2>&1 | grep -E "DOWNLOAD.*Chunk|progress"

# Paso 5: Ver de qué peers descarga cada cliente
docker logs client-2 2>&1 | grep "Descargando chunk.*de" | tail -20
docker logs client-3 2>&1 | grep "Descargando chunk.*de" | tail -20
```

### 4. Test de Announce Periódico

```bash
# Ver announces durante la descarga (cada 5 chunks o 30s)
docker logs client-2 -f 2>&1 | grep "Anunciando progreso"
```

### 5. Test de Registro Temprano (Seeding durante Descarga)

```bash
# Verificar que client-2 sirve chunks mientras descarga
docker logs client-2 2>&1 | grep "Archivo registrado para seeding" | tail -10
docker logs client-2 2>&1 | grep "Sirviendo chunk" | tail -20
```

### 6. Test de Tolerancia a Fallos de Trackers

```bash
# Detener tracker-1
docker stop tracker-1

# Ver si los clientes rotan a otro tracker
docker logs client-1 2>&1 | grep -E "Error.*tracker|rotando|siguiente tracker" | tail -20

# Ver announce en tracker alternativo
docker logs client-1 2>&1 | grep "Announce exitoso" | tail -5

# Levantar tracker-1 nuevamente
docker start tracker-1
```

### 7. Test de Replicación entre Trackers

```bash
# Registrar torrent en tracker-1
# Ver si se replica en tracker-2
docker logs tracker-2 2>&1 | grep -E "event|replication|apply_event" | tail -30

# Ver vector clocks
docker logs tracker-2 2>&1 | grep -E "VectorClock|causal" | tail -20
```

### 8. Test de Verificación de Hashes

```bash
# Ver verificación de chunks
docker logs client-2 2>&1 | grep -E "hash.*verified|chunk.*válido" | tail -20

# Ver fallos de verificación (si los hay)
docker logs client-2 2>&1 | grep -E "hash.*mismatch|chunk.*inválido" | tail -20
```

---

## 📊 Logs por Componente

### Cliente - Componentes Principales

#### 1. TrackerManager
```bash
# Logs de inicio y configuración
docker logs client-1 2>&1 | grep "TrackerManager iniciado"

# Logs de discovery
docker logs client-1 2>&1 | grep -E "DNS discovery|Ping sweep|Discovery encontró"

# Logs de operaciones
docker logs client-1 2>&1 | grep -E "registrado en|Obtenidos.*peers|Announce exitoso"

# Logs de errores
docker logs client-1 2>&1 | grep -E "TrackerManager.*ERROR|No se pudo.*tracker"
```

#### 2. TorrentClient
```bash
# Logs de estado de torrents
docker logs client-1 2>&1 | grep "GET_STATUS"

# Logs de descargas
docker logs client-1 2>&1 | grep -E "DOWNLOAD|descargando|progress"

# Logs de seeding
docker logs client-1 2>&1 | grep -E "SEEDING|seeding"
```

#### 3. PeerService
```bash
# Logs de servidor P2P
docker logs client-1 2>&1 | grep -E "Archivo registrado|Sirviendo chunk"

# Logs de cliente P2P
docker logs client-1 2>&1 | grep -E "Descargando chunk|Chunk.*descargado"

# Logs de conexiones
docker logs client-1 2>&1 | grep -E "Peer conectado|Peer desconectado"
```

#### 4. GUI
```bash
# Logs de actualización de UI
docker logs client-1 2>&1 | grep "GUI_UPDATE"

# Logs de discovery en GUI
docker logs client-1 2>&1 | grep -E "src.client.gui.client.*Discovery"

# Logs de errores de GUI
docker logs client-1 2>&1 | grep -E "gui.client.*ERROR"
```

### Tracker - Componentes Principales

#### 1. ClusterService
```bash
# Logs de descubrimiento de peers
docker logs tracker-1 2>&1 | grep -E "Discovery|DockerDNS|Ping sweep"

# Logs de sincronización
docker logs tracker-1 2>&1 | grep -E "cluster_sync|sync_loop"

# Logs de coordinador
docker logs tracker-1 2>&1 | grep -E "coordinator|election|Bully"

# Logs de heartbeat
docker logs tracker-1 2>&1 | grep "heartbeat"
```

#### 2. TrackerService
```bash
# Logs de announces
docker logs tracker-1 2>&1 | grep "announce"

# Logs de peer_list
docker logs tracker-1 2>&1 | grep "peer_list"

# Logs de scrape
docker logs tracker-1 2>&1 | grep "scrape"
```

#### 3. ReplicationService
```bash
# Logs de eventos de replicación
docker logs tracker-1 2>&1 | grep -E "event|replication"

# Logs de aplicación de eventos
docker logs tracker-1 2>&1 | grep "apply_event"
```

#### 4. CleanupService
```bash
# Logs de limpieza de peers
docker logs tracker-1 2>&1 | grep -E "cleanup|inactive.*peers|removed.*peers"

# Logs de limpieza de torrents
docker logs tracker-1 2>&1 | grep -E "orphaned.*torrents|removed.*torrents"

# Logs de limpieza de eventos
docker logs tracker-1 2>&1 | grep -E "purged.*events|removed.*events"
```

---

## 🤖 Scripts de Testing Automatizados

### Script 1: Monitoreo Completo del Sistema

```bash
#!/bin/bash
# monitor_system.sh

echo "=== ESTADO DE CONTENEDORES ==="
docker compose -f docker-compose-4trackers.yml ps

echo -e "\n=== TRACKERS DESCUBIERTOS (CLIENT-1) ==="
docker logs client-1 2>&1 | grep "Tracker añadido" | tail -10

echo -e "\n=== TRACKER ACTUAL (CLIENT-1) ==="
docker logs client-1 2>&1 | grep "tracker principal" | tail -1

echo -e "\n=== CLUSTER DE TRACKERS ==="
for i in 1 2 3 4; do
  echo "--- Tracker-$i ---"
  docker logs tracker-$i 2>&1 | grep -E "coordinator|cluster size" | tail -2
done

echo -e "\n=== TORRENTS ACTIVOS ==="
docker logs client-1 2>&1 | grep "GUI_UPDATE.*Torrent:" | tail -5

echo -e "\n=== ÚLTIMAS DESCARGAS ==="
docker logs client-1 2>&1 | grep "DOWNLOAD.*Chunk.*descargado" | tail -10
```

### Script 2: Test de Descarga P2P Completo

```bash
#!/bin/bash
# test_p2p_download.sh

FILE_SIZE=$1  # En MB
FILE_NAME="test_$(date +%s).bin"

echo "Creando archivo de ${FILE_SIZE}MB en client-1..."
docker exec client-1 bash -c "dd if=/dev/urandom of=/app/downloads/${FILE_NAME} bs=1M count=${FILE_SIZE} 2>/dev/null"

echo "Esperando 5 segundos..."
sleep 5

echo "Monitoreando descarga en client-2..."
docker logs client-2 -f 2>&1 | grep -E "DOWNLOAD.*${FILE_NAME}|progress.*${FILE_NAME}" &
PID1=$!

echo "Monitoreando descarga en client-3..."
docker logs client-3 -f 2>&1 | grep -E "DOWNLOAD.*${FILE_NAME}|progress.*${FILE_NAME}" &
PID2=$!

# Esperar 60 segundos o hasta completar
sleep 60

kill $PID1 $PID2 2>/dev/null

echo -e "\n=== RESUMEN DE DESCARGA ==="
echo "Client-2:"
docker logs client-2 2>&1 | grep "${FILE_NAME}" | tail -5
echo "Client-3:"
docker logs client-3 2>&1 | grep "${FILE_NAME}" | tail -5
```

### Script 3: Test de Tolerancia a Fallos

```bash
#!/bin/bash
# test_fault_tolerance.sh

echo "Deteniendo tracker-1..."
docker stop tracker-1

echo "Esperando 10 segundos..."
sleep 10

echo "=== LOGS DE ROTACIÓN DE TRACKER ==="
docker logs client-1 2>&1 | grep -E "Error.*tracker|rotando" | tail -10

echo "=== VERIFICANDO ANNOUNCE EN TRACKER ALTERNATIVO ==="
docker logs client-1 2>&1 | grep "Announce exitoso" | tail -3

echo "Levantando tracker-1..."
docker start tracker-1

echo "Sistema restaurado"
```

### Script 4: Análisis de Performance

```bash
#!/bin/bash
# analyze_performance.sh

echo "=== ESTADÍSTICAS DE DESCARGA ==="
for client in client-1 client-2 client-3; do
  echo "--- $client ---"
  TOTAL_CHUNKS=$(docker logs $client 2>&1 | grep "Chunk.*descargado" | wc -l)
  echo "Chunks descargados: $TOTAL_CHUNKS"
  
  COMPLETED=$(docker logs $client 2>&1 | grep "Descarga completa" | wc -l)
  echo "Descargas completadas: $COMPLETED"
  
  ERRORS=$(docker logs $client 2>&1 | grep -i "error.*descarga" | wc -l)
  echo "Errores de descarga: $ERRORS"
  echo ""
done

echo "=== ESTADÍSTICAS DE TRACKERS ==="
for i in 1 2 3 4; do
  echo "--- Tracker-$i ---"
  ANNOUNCES=$(docker logs tracker-$i 2>&1 | grep "announce" | wc -l)
  echo "Announces recibidos: $ANNOUNCES"
  
  PEERS_CLEANED=$(docker logs tracker-$i 2>&1 | grep "removed.*peers" | tail -1)
  echo "Última limpieza: $PEERS_CLEANED"
  echo ""
done
```

### Script 5: Verificar Replicación

```bash
#!/bin/bash
# verify_replication.sh

echo "=== EVENTOS DE REPLICACIÓN ==="
for i in 1 2 3 4; do
  echo "--- Tracker-$i ---"
  docker logs tracker-$i 2>&1 | grep -E "create_event|apply_event" | tail -5
  echo ""
done

echo "=== VECTOR CLOCKS ==="
for i in 1 2 3 4; do
  echo "--- Tracker-$i ---"
  docker logs tracker-$i 2>&1 | grep "VectorClock" | tail -3
  echo ""
done
```

---

## 🔍 Comandos de Debug Avanzados

### Inspeccionar Red Docker
```bash
# Ver la red torrent_net
docker network inspect tests_torrent_net

# Ver IPs de todos los contenedores
docker network inspect tests_torrent_net | grep -E "Name|IPv4Address"
```

### Ejecutar Comandos Dentro de Contenedores
```bash
# Entrar a un contenedor
docker exec -it client-1 /bin/sh

# Ejecutar Python REPL
docker exec -it client-1 uv run python

# Ver archivos descargados
docker exec client-1 ls -lh /app/downloads/

# Ver torrents
docker exec client-1 ls -lh /app/torrents/

# Verificar hash de archivo
docker exec client-1 sha256sum /app/downloads/test_file.bin
```

### Monitoreo de Recursos
```bash
# Ver uso de recursos
docker stats

# Ver uso de recursos de un contenedor
docker stats client-1

# Ver logs de sistema
docker events --filter 'type=container'
```

---

## 📝 Patrones de Logs Importantes

### Logs de Éxito
```
✅ "TrackerManager iniciado"
✅ "Discovery encontró X trackers"
✅ "Chunk X descargado"
✅ "Descarga completa"
✅ "Announce exitoso"
✅ "Torrent.*registrado"
```

### Logs de Alerta
```
⚠️ "rotando.*tracker"
⚠️ "DNS discovery falló"
⚠️ "Ping sweep falló"
⚠️ "No se pudieron obtener peers"
```

### Logs de Error
```
❌ "ERROR.*descarga"
❌ "Error.*tracker"
❌ "hash.*mismatch"
❌ "No se pudo.*tracker"
❌ "Error en discovery"
```

---

## 🎯 Casos de Uso de Testing

### Test 1: Verificar que Discovery Funciona
```bash
docker restart client-1
sleep 10
docker logs client-1 2>&1 | grep -E "Discovery encontró|Tracker añadido"
# Esperado: Debe encontrar 4 trackers (172.29.0.11-14)
```

### Test 2: Verificar Descarga P2P
```bash
# Crear archivo en client-1
docker exec client-1 bash -c 'dd if=/dev/urandom of=/app/downloads/test.bin bs=1M count=3 2>/dev/null'

# Monitorear descarga en client-2
docker logs client-2 -f 2>&1 | grep -E "Chunk.*descargado|progress"
# Esperado: Ver progreso de chunks y 100% al final
```

### Test 3: Verificar Rotación de Trackers
```bash
docker stop tracker-1
docker logs client-1 -f 2>&1 | grep -E "Announce|Error"
# Esperado: Debe cambiar a otro tracker sin perder conectividad
```

---

**Nota:** Todos estos comandos asumen que estás en el directorio `/home/daaku/Projects/Escuela/bittorrent/tests/`
