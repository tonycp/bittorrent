# Entorno de Prueba del Cluster

## Arquitectura

3 trackers en una red Docker Bridge (`172.17.0.0/16`):

- **tracker-1** (coordinador probable)
  - RPC: `localhost:5555`
  - Cluster: `localhost:5556`
  
- **tracker-2**
  - RPC: `localhost:5557`
  - Cluster: `localhost:5558`
  
- **tracker-3**
  - RPC: `localhost:5559`
  - Cluster: `localhost:5560`

## Ejecutar Pruebas

```bash
# Ejecutar todas las pruebas
./test-cluster.sh

./tests/test-cluster.sh

# O manualmente (desde la raíz del repo):
# 1. Build de base
# O manualmente:

# 2. Levantar cluster
docker compose -p bittorrent -f tests/docker-compose.yml up -d --build

# 3. Ver logs
docker compose -p bittorrent -f tests/docker-compose.yml logs -f

# 4. Ver logs de un tracker específico
docker compose -p bittorrent -f tests/docker-compose.yml logs -f tracker-1
# 2. Levantar cluster
docker-compose up -d --build

# 3. Ver logs
docker-compose logs -f

docker compose -p bittorrent -f tests/docker-compose.yml logs | grep "discovered\|found tracker"

# Ver resultado de elección
docker compose -p bittorrent -f tests/docker-compose.yml logs | grep "coordinator\|elected"
```

## Verificar Funcionalidad

docker compose -p bittorrent -f tests/docker-compose.yml logs | grep "heartbeat"

```bash
# Ver qué trackers descubrió cada nodo
docker-compose logs | grep "discovered\|found tracker"
docker compose -p bittorrent -f tests/docker-compose.yml logs | grep "replicat"
# Ver resultado de elección
docker-compose logs | grep "coordinator\|elected"
```

### 2. Heartbeat

```bash
# Ver heartbeats entre trackers
docker-compose logs | grep "heartbeat"
```

### 3. Replicación

docker compose -p bittorrent -f tests/docker-compose.yml down

# Detener y limpiar volúmenes

docker compose -p bittorrent -f tests/docker-compose.yml down -v

# Limpiar todo (imágenes también)

docker compose -p bittorrent -f tests/docker-compose.yml down -v --rmi all
docker-compose logs | grep "replicat"

```

### 4. Estado del Cluster

```bash
docker compose -p bittorrent -f tests/docker-compose.yml stop tracker-1

# Ver nueva elección
docker compose -p bittorrent -f tests/docker-compose.yml logs tracker-2 tracker-3 | grep "election"

# Reiniciar
docker compose -p bittorrent -f tests/docker-compose.yml start tracker-1
# O inspeccionar red
docker network inspect bittorrent_torrent_net
```

## Detener y Limpiar

```bash
# Detener servicios
docker-compose down

# Detener y limpiar volúmenes
docker-compose down -v

# Limpiar todo (imágenes también)
docker-compose down -v --rmi all
```

## Pruebas Específicas

### Probar Tolerancia a Fallos

```bash
# Simular caída del coordinador
docker-compose stop tracker-1

# Ver nueva elección
docker-compose logs tracker-2 tracker-3 | grep "election"

# Reiniciar
docker-compose start tracker-1
```

### Probar Replicación

```bash
# Agregar un torrent en tracker-1
# (necesitas un cliente o script Python)

# Verificar que se replicó a tracker-2 y tracker-3
docker exec -it tracker-2 sqlite3 /app/data/tracker.db "SELECT * FROM torrents;"
```

## Problemas Comunes

### Puerto en uso

```bash
# Ver qué usa el puerto
sudo lsof -i :5555

# Cambiar puerto en docker-compose.yml
```

### Trackers no se descubren

```bash
# Verificar red Docker
docker network ls
docker network inspect bittorrent_torrent_net

# Verificar DNS interno
docker exec -it tracker-1 ping tracker-2
```

### Logs vacíos

```bash
# Verificar que el código arranca
docker-compose logs tracker-1 | head -20

# Entrar al contenedor
docker exec -it tracker-1 /bin/bash
```
