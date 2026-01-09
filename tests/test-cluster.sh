#!/bin/bash
# Script para probar el cluster de trackers

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
PROJECT_NAME="bittorrent"

echo "=== BitTorrent Distributed Tracker Test ==="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para esperar que un servicio esté listo
wait_for_service() {
    local host=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -n "Esperando que $host:$port esté listo..."
    while ! nc -z $host $port 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            echo -e " ${RED}TIMEOUT${NC}"
            return 1
        fi
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}OK${NC}"
    return 0
}

# 1. Build de la imagen base
echo -e "${YELLOW}[1/6] Building bit_lib base image...${NC}"
cd "$REPO_ROOT/bit_lib"
docker build -t bit_lib_base:latest -f Dockerfile .
cd "$REPO_ROOT"

# 2. Levantar los servicios
echo -e "${YELLOW}[2/6] Starting tracker services...${NC}"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build

# 3. Esperar a que los servicios estén listos
echo -e "${YELLOW}[3/6] Waiting for services to be ready...${NC}"
wait_for_service localhost 5555 || exit 1
wait_for_service localhost 5557 || exit 1
wait_for_service localhost 5559 || exit 1

# 4. Verificar descubrimiento de cluster
echo -e "${YELLOW}[4/6] Checking cluster discovery...${NC}"
sleep 5  # Dar tiempo para discovery inicial

echo "Tracker-1 cluster view:"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs tracker-1 | grep -i "cluster\|discovery\|election" | tail -5

echo ""
echo "Tracker-2 cluster view:"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs tracker-2 | grep -i "cluster\|discovery\|election" | tail -5

echo ""
echo "Tracker-3 cluster view:"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs tracker-3 | grep -i "cluster\|discovery\|election" | tail -5

# 5. Verificar elección de coordinador
echo -e "${YELLOW}[5/6] Checking coordinator election...${NC}"
echo "Buscando coordinador elegido..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs | grep -i "coordinator\|elected\|leader" | tail -10

# 6. Mostrar estado final
echo -e "${YELLOW}[6/6] Cluster Status${NC}"
echo ""
echo "=== Running Containers ==="
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps

echo ""
echo "=== Network Info ==="
docker network inspect ${PROJECT_NAME}_torrent_net | grep -A 5 "Containers"

echo ""
echo -e "${GREEN}=== Test Complete ===${NC}"
echo ""
echo "Para ver logs en tiempo real:"
echo "  docker compose -p $PROJECT_NAME -f $COMPOSE_FILE logs -f"
echo ""
echo "Para probar manualmente:"
echo "  docker exec -it tracker-1 python -c 'import asyncio; from src.app import main; asyncio.run(main())'"
echo ""
echo "Para detener:"
echo "  docker compose -p $PROJECT_NAME -f $COMPOSE_FILE down"
echo ""
echo "Para limpiar todo:"
echo "  docker compose -p $PROJECT_NAME -f $COMPOSE_FILE down -v"
