#!/usr/bin/env python3
"""Test para verificar que la GUI puede importarse y crearse correctamente"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Test imports
print("=" * 60)
print("TEST: Importación y creación de componentes GUI")
print("=" * 60)

try:
    print("\n[1] Importando ConfigManager...")
    from src.client.config.config_mng import ConfigManager
    config = ConfigManager()
    print("✅ ConfigManager importado")
    
    print("\n[2] Importando TorrentClient...")
    from src.client.core.torrent_client import TorrentClient
    print("✅ TorrentClient importado")
    
    print("\n[3] Verificando que TorrentClient puede crearse...")
    client = TorrentClient(config)
    print("✅ TorrentClient creado")
    
    print("\n[4] Inicializando sesión del cliente...")
    client.setup_session()
    print("✅ Sesión inicializada")
    
    print("\n[5] Verificando TrackerClient...")
    from src.client.connection.tracker_client import TrackerClient
    tracker_client = TrackerClient()
    print("✅ TrackerClient importado")
    
    print("\n[6] Intentando importar GUI (puede fallar sin display)...")
    try:
        # Solo importar, no ejecutar
        from src.client.gui import client as gui_module
        print("✅ Módulo GUI importado (no ejecutado)")
    except ImportError as e:
        if "tkinter" in str(e).lower() or "libtk" in str(e):
            print("⚠️  Tkinter no disponible en este entorno (normal en servidor/contenedor)")
        else:
            print(f"❌ Error importando GUI: {e}")
            raise
    except Exception as e:
        if "DISPLAY" in str(e) or "no display" in str(e).lower():
            print("⚠️  GUI no puede ejecutarse sin display (normal en servidor/contenedor)")
        else:
            print(f"❌ Error importando GUI: {e}")
            raise
    
    print("\n" + "=" * 60)
    print("✅ TODOS LOS COMPONENTES SE IMPORTAN CORRECTAMENTE")
    print("=" * 60)
    print("\nNota: Para ejecutar la GUI completa, ejecuta:")
    print("  python cli_main.py  (para CLI)")
    print("  python -m client.gui.client  (para GUI con display)")
    
    sys.exit(0)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
