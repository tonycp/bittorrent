#!/usr/bin/env python3
"""
Test Funcional Completo del Cliente BitTorrent

Valida todas las funcionalidades:
1. Configuración
2. Comunicación con tracker (registro, announce, get_peers)
3. TorrentClient (adaptador GUI)
4. ClientManager (coordinador)
5. TrackerManager (tracker comms)
6. CLI (importación)
7. GUI (importación y creación con mock si tkinter no está disponible)
"""

import sys
import asyncio
import json
import tempfile
from pathlib import Path
from uuid import uuid4

# Configurar path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_test(text):
    print(f"{Colors.BOLD}[TEST]{Colors.END} {text}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"   {text}")


# ============================================================
# TEST 1: Configuración
# ============================================================
def test_config():
    print_header("TEST 1: Configuración")
    
    try:
        print_test("Importando ConfigManager...")
        from src.client.config.config_mng import ConfigManager
        print_success("ConfigManager importado")
        
        print_test("Creando configuración...")
        config = ConfigManager()
        print_success("Configuración creada")
        
        print_test("Verificando parámetros...")
        tracker_host, tracker_port = config.get_tracker_address()
        listen_port = config.get_listen_port()
        download_path = config.get("General", "download_path")
        
        print_info(f"Tracker: {tracker_host}:{tracker_port}")
        print_info(f"Listen port: {listen_port}")
        print_info(f"Download path: {download_path}")
        print_success("Parámetros correctos")
        
        return True, config
    except Exception as e:
        print_error(f"Error en configuración: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# ============================================================
# TEST 2: TrackerClient (bit_lib)
# ============================================================
async def test_tracker_client():
    print_header("TEST 2: TrackerClient (bit_lib)")
    
    try:
        print_test("Importando TrackerClient...")
        from src.client.connection.tracker_client import TrackerClient
        print_success("TrackerClient importado")
        
        print_test("Iniciando TrackerClient...")
        client = TrackerClient()
        await client.start()
        print_success("TrackerClient iniciado")
        
        # Test registro
        print_test("Registrando torrent de prueba...")
        test_hash = uuid4().hex[:16]
        result = await client.register_torrent(
            tracker_host="localhost",
            tracker_port=5555,
            torrent_hash=test_hash,
            file_name="test_file.txt",
            file_size=1024000,
            total_chunks=63,
            piece_length=16384
        )
        print_success("Torrent registrado")
        print_info(f"Hash: {test_hash}")
        
        # Test announce
        print_test("Anunciando peer...")
        await client.announce_peer(
            tracker_host="localhost",
            tracker_port=5555,
            tracker_id="localhost:5555",
            peer_id="test-peer-functional",
            torrent_hash=test_hash,
            ip="192.168.1.100",
            port=6881,
            uploaded=0,
            downloaded=0,
            left=1024000
        )
        print_success("Peer anunciado")
        
        # Test get_peers
        print_test("Obteniendo lista de peers...")
        peers = await client.get_peers(
            tracker_host="localhost",
            tracker_port=5555,
            torrent_hash=test_hash
        )
        print_success(f"Obtenidos {len(peers)} peers")
        if peers:
            print_info(f"Primer peer: {peers[0].get('peer_id')} @ {peers[0].get('ip')}:{peers[0].get('port')}")
        
        # Cleanup
        await client.stop()
        print_success("TrackerClient detenido")
        
        return True, test_hash
    except Exception as e:
        print_error(f"Error en TrackerClient: {e}")
        import traceback
        traceback.print_exc()
        return False, None


# ============================================================
# TEST 3: TrackerManager
# ============================================================
async def test_tracker_manager(config):
    print_header("TEST 3: TrackerManager")
    
    try:
        print_test("Importando TrackerManager...")
        from src.client.core.tracker_manager import TrackerManager
        print_success("TrackerManager importado")
        
        print_test("Creando TrackerManager...")
        manager = TrackerManager(config)
        print_success("TrackerManager creado (sin NetworkManager)")
        
        print_test("Iniciando TrackerManager...")
        await manager.start()
        print_success("TrackerManager iniciado")
        
        print_test("Verificando obtención de IP...")
        ip = manager._get_client_ip()
        print_info(f"Client IP: {ip}")
        print_success("IP obtenida correctamente")
        
        # Test registro a través del manager
        print_test("Registrando torrent a través del manager...")
        test_hash = uuid4().hex[:16]
        await manager.register_torrent_async(
            torrent_hash=test_hash,
            file_name="test_manager.txt",
            file_size=2048000,
            total_chunks=125,
            piece_length=16384
        )
        print_success("Torrent registrado vía manager")
        print_info(f"Hash: {test_hash}")
        
        # Cleanup
        await manager.stop()
        print_success("TrackerManager detenido")
        
        return True
    except Exception as e:
        print_error(f"Error en TrackerManager: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 4: ClientManager
# ============================================================
def test_client_manager(config):
    print_header("TEST 4: ClientManager")
    
    try:
        print_test("Importando ClientManager...")
        from src.client.core.client_manager import ClientManager
        print_success("ClientManager importado")
        
        print_test("Creando ClientManager (sin NetworkManager)...")
        manager = ClientManager(config)
        print_success("ClientManager creado")
        
        print_test("Verificando atributos...")
        assert hasattr(manager, 'tracker_manager'), "Debe tener tracker_manager"
        assert hasattr(manager, 'peer_id'), "Debe tener peer_id"
        assert hasattr(manager, '_torrents'), "Debe tener _torrents"
        assert not hasattr(manager, 'peer_service') or manager.peer_service is None, "No debe tener peer_service"
        print_success("Atributos correctos")
        
        print_test("Iniciando ClientManager...")
        manager.start()
        print_success("ClientManager iniciado")
        
        print_test("Verificando servicios...")
        # Dar tiempo para que se inicien los servicios
        import time
        time.sleep(1)
        assert manager.tracker_manager is not None, "TrackerManager debe estar inicializado"
        print_success("TrackerManager activo")
        
        print_test("Deteniendo ClientManager...")
        manager.stop()
        print_success("ClientManager detenido")
        
        return True
    except Exception as e:
        print_error(f"Error en ClientManager: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 5: TorrentClient (Adaptador GUI)
# ============================================================
def test_torrent_client(config):
    print_header("TEST 5: TorrentClient (Adaptador GUI)")
    
    try:
        print_test("Importando TorrentClient...")
        from src.client.core.torrent_client import TorrentClient
        print_success("TorrentClient importado")
        
        print_test("Creando TorrentClient...")
        client = TorrentClient(config)
        print_success("TorrentClient creado")
        
        print_test("Configurando sesión...")
        client.setup_session()
        print_success("Sesión configurada")
        
        print_test("Verificando ClientManager creado...")
        assert client.client_manager is not None, "ClientManager debe estar creado"
        assert client._initialized, "Cliente debe estar inicializado"
        print_success("ClientManager creado y activo")
        
        print_test("Verificando TrackerManager activo...")
        import time
        time.sleep(1)
        assert client.client_manager.tracker_manager is not None, "TrackerManager debe estar activo"
        print_success("TrackerManager activo")
        
        # Cleanup
        print_test("Deteniendo cliente...")
        client.client_manager.stop()
        print_success("Cliente detenido")
        
        return True
    except Exception as e:
        print_error(f"Error en TorrentClient: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 6: CLI
# ============================================================
def test_cli():
    print_header("TEST 6: CLI")
    
    try:
        print_test("Importando componentes del CLI...")
        from src.cli.cli_standalone import BitTorrentCLI
        print_success("CLI importado")
        
        print_test("Verificando que cmd.Cmd está disponible...")
        import cmd
        assert issubclass(BitTorrentCLI, cmd.Cmd), "CLI debe heredar de cmd.Cmd"
        print_success("CLI hereda correctamente de cmd.Cmd")
        
        print_info("Nota: CLI completo requiere ejecución interactiva")
        print_success("CLI importable y estructura correcta")
        
        return True
    except Exception as e:
        print_error(f"Error en CLI: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 7: GUI (con manejo de tkinter faltante)
# ============================================================
def test_gui():
    print_header("TEST 7: GUI")
    
    try:
        print_test("Verificando disponibilidad de tkinter...")
        tkinter_available = False
        try:
            import tkinter
            tkinter_available = True
            print_success("tkinter disponible")
        except ImportError:
            print_warning("tkinter no disponible (normal en servidor/contenedor)")
            print_info("Se omitirá test de creación de ventana")
        
        print_test("Importando módulo GUI...")
        try:
            from src.client.gui import client as gui_module
            if tkinter_available:
                print_success("Módulo GUI importado")
                
                print_test("Verificando clase BitTorrentClient...")
                assert hasattr(gui_module, 'BitTorrentClient'), "Debe tener BitTorrentClient"
                print_success("BitTorrentClient disponible")
                
                print_info("Para test completo de GUI, ejecutar en entorno con display")
            else:
                print_warning("GUI no importado (tkinter faltante)")
                print_info("Código GUI está intacto, solo falta librería de sistema")
        except ImportError as e:
            if "tkinter" in str(e).lower() or "libtk" in str(e):
                print_warning("GUI requiere tkinter system package")
                print_info("Instalar con: apt install python3-tk")
            else:
                raise
        
        return True
    except Exception as e:
        print_error(f"Error inesperado en GUI: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 8: Integración End-to-End
# ============================================================
def test_e2e_integration(config):
    print_header("TEST 8: Integración End-to-End")
    
    try:
        print_test("Creando archivo .p2p de prueba...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.p2p', delete=False) as f:
            test_data = {
                "info_hash": uuid4().hex[:16],
                "file_name": "test_e2e.txt",
                "file_size": 512000,
                "chunk_size": 16384,
                "total_chunks": 32
            }
            json.dump(test_data, f)
            torrent_file = f.name
        print_success(f"Archivo creado: {torrent_file}")
        
        print_test("Cargando torrent con TorrentClient...")
        from src.client.core.torrent_client import TorrentClient, TorrentInfo
        
        client = TorrentClient(config)
        client.setup_session()
        
        torrent_info = TorrentInfo.from_torrent_file(Path(torrent_file))
        print_success(f"Torrent cargado: {torrent_info.file_name}")
        print_info(f"Hash: {torrent_info.file_hash}")
        print_info(f"Size: {torrent_info.display_size}")
        
        print_test("Añadiendo torrent (registrará en tracker)...")
        import time
        time.sleep(1)  # Dar tiempo para que TrackerManager se inicie
        
        handle = client.add_torrent(torrent_info)
        print_success(f"Torrent añadido con handle: {handle[:8]}...")
        
        # Cleanup
        import os
        os.unlink(torrent_file)
        client.client_manager.stop()
        print_success("Cleanup completado")
        
        return True
    except Exception as e:
        print_error(f"Error en integración E2E: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# MAIN
# ============================================================
async def main():
    print_header("TEST FUNCIONAL COMPLETO - CLIENTE BITTORRENT")
    
    results = {}
    
    # Test 1: Config
    success, config = test_config()
    results['Config'] = success
    if not success:
        print_error("Test de configuración falló, abortando...")
        return results
    
    # Test 2: TrackerClient
    success, test_hash = await test_tracker_client()
    results['TrackerClient'] = success
    
    # Test 3: TrackerManager
    success = await test_tracker_manager(config)
    results['TrackerManager'] = success
    
    # Test 4: ClientManager
    success = test_client_manager(config)
    results['ClientManager'] = success
    
    # Test 5: TorrentClient
    success = test_torrent_client(config)
    results['TorrentClient'] = success
    
    # Test 6: CLI
    success = test_cli()
    results['CLI'] = success
    
    # Test 7: GUI
    success = test_gui()
    results['GUI'] = success
    
    # Test 8: E2E Integration
    success = test_e2e_integration(config)
    results['E2E Integration'] = success
    
    # Resumen
    print_header("RESUMEN DE TESTS")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for test_name, success in results.items():
        if success:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{Colors.BOLD}Total: {total} | Pasados: {passed} | Fallidos: {failed}{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*70}")
        print("🎉 TODOS LOS TESTS PASARON EXITOSAMENTE 🎉".center(70))
        print(f"{'='*70}{Colors.END}\n")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*70}")
        print(f"❌ {failed} TEST(S) FALLARON".center(70))
        print(f"{'='*70}{Colors.END}\n")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrumpido por usuario{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error fatal: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
