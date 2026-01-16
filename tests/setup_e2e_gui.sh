#!/bin/bash
# Setup script for E2E GUI test
# Prepara el entorno para ejecutar clientes con GUI en Docker

set -e

echo "================================================"
echo "  Preparando entorno para test E2E con GUI"
echo "================================================"
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check OS
echo -e "${BLUE}[1/5]${NC} Detectando sistema operativo..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo -e "${GREEN}✓${NC} Linux detectado"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
    echo -e "${GREEN}✓${NC} macOS detectado"
else
    OS="other"
    echo -e "${YELLOW}⚠${NC} Sistema desconocido: $OSTYPE"
fi
echo

# Check Docker
echo -e "${BLUE}[2/5]${NC} Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗${NC} Docker no está instalado"
    echo "Instala Docker desde: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker instalado: $(docker --version)"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗${NC} docker-compose no está instalado"
    echo "Instala docker-compose desde: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓${NC} docker-compose instalado: $(docker-compose --version)"
echo

# Setup X11
echo -e "${BLUE}[3/5]${NC} Configurando X11 para GUI..."

if [ "$OS" = "linux" ]; then
    # Linux: permitir conexiones locales de Docker
    if command -v xhost &> /dev/null; then
        xhost +local:docker > /dev/null 2>&1 || true
        echo -e "${GREEN}✓${NC} X11 configurado para Docker (xhost +local:docker)"
        
        # Verificar DISPLAY
        if [ -z "$DISPLAY" ]; then
            export DISPLAY=:0
            echo -e "${YELLOW}⚠${NC} DISPLAY no estaba configurado, usando :0"
        fi
        echo -e "${GREEN}✓${NC} DISPLAY=$DISPLAY"
        
        # Verificar socket X11
        if [ ! -S /tmp/.X11-unix/X0 ]; then
            echo -e "${YELLOW}⚠${NC} Socket X11 no encontrado en /tmp/.X11-unix/X0"
            echo "   Asegúrate de que X11 esté ejecutándose"
        else
            echo -e "${GREEN}✓${NC} Socket X11 disponible"
        fi
    else
        echo -e "${YELLOW}⚠${NC} xhost no encontrado"
        echo "   Instala: sudo apt-get install x11-xserver-utils"
    fi
    
elif [ "$OS" = "mac" ]; then
    # macOS: necesita X11 server (XQuartz)
    if command -v xquartz &> /dev/null || [ -d "/Applications/Utilities/XQuartz.app" ]; then
        echo -e "${GREEN}✓${NC} XQuartz instalado"
        
        # Verificar si está corriendo
        if pgrep -x "Xquartz" > /dev/null; then
            echo -e "${GREEN}✓${NC} XQuartz ejecutándose"
        else
            echo -e "${YELLOW}⚠${NC} XQuartz no está ejecutándose"
            echo "   Inicia XQuartz desde Applications/Utilities"
        fi
        
        # Configurar display
        if [ -z "$DISPLAY" ]; then
            export DISPLAY=host.docker.internal:0
            echo -e "${YELLOW}⚠${NC} DISPLAY configurado a host.docker.internal:0"
        fi
        echo -e "${GREEN}✓${NC} DISPLAY=$DISPLAY"
        
        # Permitir conexiones
        xhost + $(hostname) > /dev/null 2>&1 || true
        echo -e "${GREEN}✓${NC} Conexiones X11 permitidas"
    else
        echo -e "${RED}✗${NC} XQuartz no está instalado"
        echo "   Instala desde: https://www.xquartz.org/"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠${NC} Configuración X11 manual puede ser necesaria"
fi
echo

# Check bit_lib
echo -e "${BLUE}[4/5]${NC} Verificando bit_lib..."
if [ -d "../bit_lib" ]; then
    echo -e "${GREEN}✓${NC} bit_lib encontrado"
else
    echo -e "${RED}✗${NC} bit_lib no encontrado en ../bit_lib"
    exit 1
fi
echo

# Build images
echo -e "${BLUE}[5/5]${NC} Construyendo imágenes Docker..."
echo -e "${YELLOW}ℹ${NC} Esto puede tardar varios minutos la primera vez..."
echo

docker-compose -f docker-compose-e2e-gui.yml build --no-cache

if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}✓${NC} Imágenes construidas exitosamente"
else
    echo
    echo -e "${RED}✗${NC} Error construyendo imágenes"
    exit 1
fi

echo
echo "================================================"
echo -e "${GREEN}  ✓ Entorno preparado correctamente${NC}"
echo "================================================"
echo
echo "Siguiente paso:"
echo "  $ python test_e2e_gui_complete.py"
echo
echo "O manualmente:"
echo "  $ docker-compose -f docker-compose-e2e-gui.yml up -d"
echo
echo "Para ver logs:"
echo "  $ docker-compose -f docker-compose-e2e-gui.yml logs -f"
echo
echo "Para detener:"
echo "  $ docker-compose -f docker-compose-e2e-gui.yml down -v"
echo
