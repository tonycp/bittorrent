#!/usr/bin/env python3
"""
CLI para el cliente BitTorrent - Independiente (sin dependencias del __init__.py)
"""

import cmd
import sys
import time
import logging
from pathlib import Path
from typing import Optional

# Importar solo lo necesario, sin usar el __init__.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from tabulate import tabulate
except ImportError:
    print("Error: tabulate no está instalado")
    print("Instala con: pip install tabulate")
    sys.exit(1)

# Importar componentes directamente sin pasar por __init__.py
from src.client.core.torrent_client import TorrentClient
from src.client.config.config_mng import ConfigManager

logger = logging.getLogger(__name__)


class BitTorrentCLI(cmd.Cmd):
    """CLI interactivo para cliente BitTorrent"""

    intro = """
╔═══════════════════════════════════════════════════════════════╗
║          BitTorrent Client - Command Line Interface          ║
║                                                               ║
║  Escribe 'help' para ver comandos disponibles                ║
║  Escribe 'exit' o 'quit' para salir                          ║
╚═══════════════════════════════════════════════════════════════╝
"""

    prompt = "bittorrent> "

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.client: Optional[TorrentClient] = None
        self._running = False

        # Auto-inicializar cliente
        self._init_client()

    def _init_client(self):
        """Inicializa el cliente BitTorrent"""
        try:
            self.client = TorrentClient(self.config)
            self.client.setup_session()
            self._running = True
            print("✓ Cliente BitTorrent iniciado correctamente")
            self._print_config_summary()
        except Exception as e:
            print(f"✗ Error iniciando cliente: {e}")
            logger.error(f"Error en init: {e}", exc_info=True)

    def _print_config_summary(self):
        """Imprime resumen de configuración"""
        try:
            tracker_host, tracker_port = self.config.get_tracker_address()
            download_path = self.config.get("General", "download_path")
            listen_port = self.config.get_listen_port()
            peer_id = (
                self.client.client_manager.peer_id
                if self.client.client_manager
                else "N/A"
            )

            print(f"""
Configuración actual:
  • Carpeta de descargas: {download_path}
  • Puerto de escucha: {listen_port}
  • Tracker principal: {tracker_host}:{tracker_port}
  • Peer ID: {peer_id[:8]}...
""")
        except Exception as e:
            print(f"⚠ Error al mostrar config: {e}")

    # ==================== Comandos de Torrent ====================

    def do_add(self, arg):
        """
        Añade un torrent para descargar.

        Uso: add <ruta_archivo.p2p>
        """
        if not arg:
            print("✗ Error: Debes especificar la ruta del archivo .p2p")
            return

        try:
            torrent_path = Path(arg.strip())

            if not torrent_path.exists():
                print(f"✗ Error: Archivo no encontrado: {torrent_path}")
                return

            info = self.client.get_torrent_info(str(torrent_path))

            print(f"""
Información del torrent:
  • Nombre: {info.file_name}
  • Hash: {info.file_hash[:16]}...
  • Tamaño: {info.display_size}
  • Chunks: {info.total_chunks}
""")

            confirm = input("¿Añadir este torrent? (s/n): ").strip().lower()
            if confirm != "s":
                print("✗ Operación cancelada")
                return

            self.client.add_torrent(info)
            print(f"✓ Torrent añadido: {info.file_name}")

        except Exception as e:
            print(f"✗ Error: {e}")
            logger.error(f"Error en add: {e}", exc_info=True)

    def do_list(self, arg):
        """Lista todos los torrents activos."""
        try:
            handles = self.client.get_all_torrents()

            if not handles:
                print("No hay torrents activos")
                return

            data = []
            for handle in handles:
                status = self.client.get_status(handle)
                data.append(
                    [
                        handle[:8] + "...",
                        status.file_name[:30],
                        f"{status.progress:.1f}%",
                        f"{status.downloaded_size:.1f} MB",
                        f"{status.file_size:.1f} MB",
                        status.peers,
                    ]
                )

            headers = ["Handle", "Nombre", "Progreso", "Descargado", "Tamaño", "Peers"]
            print("\n" + tabulate(data, headers=headers, tablefmt="grid"))
            print(f"\nTotal: {len(handles)} torrent(s)\n")

        except Exception as e:
            print(f"✗ Error: {e}")

    def do_ls(self, arg):
        """Alias de 'list'"""
        self.do_list(arg)

    def do_info(self, arg):
        """Muestra información de un torrent. Uso: info <handle>"""
        if not arg:
            print("✗ Uso: info <handle>")
            return

        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return

            status = self.client.get_status(handle)

            print(f"""
Información del torrent:
  • Handle: {handle[:16]}...
  • Nombre: {status.file_name}
  • Tamaño: {status.file_size:.2f} MB
  • Descargado: {status.downloaded_size:.2f} MB
  • Progreso: {status.progress:.1f}%
  • Peers activos: {status.peers}
""")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_pause(self, arg):
        """Pausa un torrent. Uso: pause <handle>"""
        if not arg:
            print("✗ Uso: pause <handle>")
            return

        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            self.client.pause_torrent(handle)
            print(f"✓ Torrent pausado")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_resume(self, arg):
        """Reanuda un torrent. Uso: resume <handle>"""
        if not arg:
            print("✗ Uso: resume <handle>")
            return

        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            self.client.resume_torrent(handle)
            print(f"✓ Torrent reanudado")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_remove(self, arg):
        """Elimina un torrent. Uso: remove <handle>"""
        if not arg:
            print("✗ Uso: remove <handle>")
            return

        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            self.client.remove_torrent(handle)
            print(f"✓ Torrent eliminado")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_rm(self, arg):
        """Alias de 'remove'"""
        self.do_remove(arg)

    def do_watch(self, arg):
        """Monitorea progreso en tiempo real. Presiona Ctrl+C para detener."""
        try:
            print("Monitoreando torrents (Ctrl+C para detener)...\n")

            while True:
                print("\033[2J\033[H", end="")

                handles = self.client.get_all_torrents()
                if not handles:
                    print("No hay torrents para monitorear")
                    break

                data = []
                for handle in handles:
                    status = self.client.get_status(handle)
                    bar_width = 20
                    filled = int(bar_width * status.progress / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)

                    data.append(
                        [
                            handle[:8] + "...",
                            status.file_name[:25],
                            bar,
                            f"{status.progress:.1f}%",
                            status.peers,
                        ]
                    )

                headers = ["Handle", "Nombre", "Progreso", "%", "Peers"]
                print(tabulate(data, headers=headers, tablefmt="grid"))
                print(f"\nActualizado: {time.strftime('%H:%M:%S')}\n")

                time.sleep(2)

        except KeyboardInterrupt:
            print("\n✓ Monitoreo detenido")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_config(self, arg):
        """Muestra o modifica configuración."""
        if not arg:
            self._print_config_summary()
            return

        args = arg.split()
        if args[0] == "set" and len(args) >= 3:
            key = args[1]
            value = " ".join(args[2:])

            try:
                if key == "download_path":
                    self.config.set("General", "download_path", value)
                elif key == "listen_port":
                    self.config.set("General", "listen_port", value)
                else:
                    print(f"✗ Key desconocido: {key}")
                    return

                print(f"✓ Configuración actualizada: {key} = {value}")
                print("⚠ Reinicia el cliente para aplicar cambios")
            except Exception as e:
                print(f"✗ Error: {e}")

    def do_restart(self, arg):
        """Reinicia el cliente."""
        try:
            print("Reiniciando cliente...")
            if self.client:
                self.client.stop()
            self._init_client()
            print("✓ Cliente reiniciado")
        except Exception as e:
            print(f"✗ Error: {e}")

    def do_exit(self, arg):
        """Sale del CLI."""
        print("\nDeteniendo cliente...")
        if self.client:
            try:
                self.client.stop()
                print("✓ Cliente detenido")
            except Exception as e:
                print(f"⚠ Error: {e}")
        print("Hasta luego!")
        return True

    def do_quit(self, arg):
        """Alias de 'exit'"""
        return self.do_exit(arg)

    def do_q(self, arg):
        """Alias de 'exit'"""
        return self.do_exit(arg)

    def do_clear(self, arg):
        """Limpia la pantalla."""
        print("\033[2J\033[H", end="")

    def do_debug(self, arg):
        """Muestra información de debug."""
        try:
            if not self.client or not self.client.client_manager:
                print("⚠ Cliente no inicializado")
                return

            cm = self.client.client_manager
            print(f"""
=== Debug Info ===
Cliente inicializado: {self._running}
Event loop activo: {cm._loop is not None}
Torrents registrados: {len(cm._torrents)}

=== Servicios ===
TrackerManager: {"Activo" if cm.tracker_manager else "Inactivo"}
""")
        except Exception as e:
            print(f"✗ Error: {e}")

    def _resolve_handle(self, prefix: str) -> Optional[str]:
        """Resuelve prefijo a handle completo"""
        handles = self.client.get_all_torrents()
        matching = [h for h in handles if h.startswith(prefix)]

        if not matching:
            print(f"✗ Torrent no encontrado: {prefix}")
            return None

        if len(matching) > 1:
            print(f"✗ Handle ambiguo, especifica más caracteres")
            return None

        return matching[0]

    def emptyline(self):
        pass

    def default(self, line):
        print(f"✗ Comando no reconocido: {line}")


def main():
    """Entry point del CLI"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("bittorrent_cli.log"),
        ],
    )

    try:
        cli = BitTorrentCLI()
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\nInterrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error fatal: {e}")
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
