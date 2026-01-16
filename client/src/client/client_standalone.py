#!/usr/bin/env python3
"""
BitTorrent Client - GUI Standalone Entry Point
Ejecuta la interfaz gráfica del cliente BitTorrent
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.client.const.env import DEBUG
from src.client.config.utils import get_env_settings
from src.client.gui import BitTorrentClientGUI
import tkinter as tk
import traceback
import debugpy


def main():
    """Entry point for GUI client"""
    load_dotenv()
    
    # Configurar logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    settings = get_env_settings()
    
    # Debug mode
    if settings.get(DEBUG, False):
        debugpy.listen(("0.0.0.0", 5678))
        print("⏳ Esperando debugger VS Code en puerto 5678...")
        debugpy.wait_for_client()
        print("✅ Debugger conectado")
    
    try:
        print("🚀 Iniciando BitTorrent Client GUI...")
        root = tk.Tk()
        app = BitTorrentClientGUI(root)
        print("✅ GUI iniciada correctamente")
        root.mainloop()
    except Exception as e:
        print(f"❌ Error iniciando GUI: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
