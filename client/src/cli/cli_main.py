#!/usr/bin/env python3
"""
Entry point para el CLI del cliente BitTorrent.

Usa cli_standalone.py para evitar dependencias del __init__.py
"""
import sys
from pathlib import Path

# Importar desde el CLI standalone
sys.path.insert(0, str(Path(__file__).parent))

from cli_standalone import main

if __name__ == "__main__":
    main()
