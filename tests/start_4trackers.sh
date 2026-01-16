#!/bin/bash
# Script para levantar la infraestructura de 4 trackers + 2 clientes GUI

set -e

echo "🚀 Levantando infraestructura BitTorrent..."
echo ""

# Configurar X11 para GUIs
echo "📺 Configurando X11 para GUIs..."
xhost +local:docker 2>/dev/null || echo "⚠️  xhost no disponible (GUIs no funcionarán)"

# Construir imágenes si es necesario
echo ""
echo "🔨 Construyendo imágenes (si es necesario)..."
docker-compose -f docker-compose-4trackers.yml build

# Limpiar contenedores anteriores
echo ""
echo "🧹 Limpiando contenedores anteriores..."
docker-compose -f docker-compose-4trackers.yml down -v

# Levantar infraestructura
echo ""
echo "🚀 Levantando contenedores..."
docker-compose -f docker-compose-4trackers.yml up -d

# Esperar que los trackers estén listos
echo ""
echo "⏳ Esperando que los trackers estén listos..."
sleep 10

# Verificar estado
echo ""
echo "✅ Verificando estado..."
docker-compose -f docker-compose-4trackers.yml ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Infraestructura levantada exitosamente!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Servicios disponibles:"
echo "  • 4 Trackers: tracker-1 a tracker-4 (puertos 5555-5562)"
echo "  • 2 Clientes GUI: client-1 y client-2"
echo ""
echo "🖥️  Para ver las GUIs, asegúrate de tener X11 configurado:"
echo "  export DISPLAY=:0"
echo "  xhost +local:docker"
echo ""
echo "📝 Ver logs:"
echo "  docker logs -f client-1"
echo "  docker logs -f tracker-1"
echo ""
echo "🔍 Ver estado del cluster:"
echo "  docker exec tracker-1 cat /app/data/cluster_state.json"
echo ""
echo "🛑 Para detener:"
echo "  docker-compose -f docker-compose-4trackers.yml down"
echo ""
