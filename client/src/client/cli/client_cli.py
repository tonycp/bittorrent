"""
CLI para el cliente BitTorrent - Interfaz de línea de comandos completa.

Permite todas las operaciones disponibles en la GUI:
- Gestión de torrents (añadir, pausar, reanudar, eliminar)
- Creación de torrents
- Monitoreo de descargas
- Configuración del cliente
- Conexión manual a peers (debug)
"""
import cmd
import sys
import time
import logging
from pathlib import Path
from typing import Optional

try:
    from tabulate import tabulate
except ImportError:
    # Fallback simple si tabulate no está disponible
    def tabulate(data, headers=None, tablefmt=None):
        if not data:
            return "No data"
        # Simple text formatting
        result = []
        if headers:
            result.append(" | ".join(str(h) for h in headers))
            result.append("-" * 80)
        for row in data:
            result.append(" | ".join(str(c) for c in row))
        return "\n".join(result)

from ..core.torrent_client import TorrentClient, TorrentInfo
from ..config.config_mng import ConfigManager

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
        tracker_host, tracker_port = self.config.get_tracker_address()
        print(f"""
Configuración actual:
  • Carpeta de descargas: {self.config.get_download_path()}
  • Carpeta de torrents: {self.config.get('General', 'torrent_path')}
  • Puerto de escucha: {self.config.get_listen_port()}
  • Tracker principal: {tracker_host}:{tracker_port}
  • Peer ID: {self.client.client_manager.peer_id[:8]}...
""")
    
    # ==================== Comandos de Torrent ====================
    
    def do_add(self, arg):
        """
        Añade un torrent para descargar.
        
        Uso: add <ruta_archivo.p2p>
        Ejemplo: add /path/to/file.p2p
        """
        if not arg:
            print("✗ Error: Debes especificar la ruta del archivo .p2p")
            print("Uso: add <ruta_archivo.p2p>")
            return
        
        try:
            torrent_path = Path(arg.strip())
            
            if not torrent_path.exists():
                print(f"✗ Error: Archivo no encontrado: {torrent_path}")
                return
            
            # Cargar info del torrent
            info = self.client.get_torrent_info(str(torrent_path))
            
            print(f"""
Información del torrent:
  • Nombre: {info.file_name}
  • Hash: {info.file_hash[:16]}...
  • Tamaño: {info.display_size}
  • Chunks: {info.total_chunks}
  • Chunk size: {info.chunk_size} bytes
""")
            
            # Confirmar
            confirm = input("¿Añadir este torrent? (s/n): ").strip().lower()
            if confirm != 's':
                print("✗ Operación cancelada")
                return
            
            # Añadir torrent
            handle = self.client.add_torrent(info)
            print(f"✓ Torrent añadido: {info.file_name}")
            print(f"  Handle: {handle[:8]}...")
            print(f"  La descarga ha comenzado automáticamente")
            
        except Exception as e:
            print(f"✗ Error añadiendo torrent: {e}")
            logger.error(f"Error en add: {e}", exc_info=True)
    
    def do_list(self, arg):
        """
        Lista todos los torrents activos.
        
        Uso: list
        Alias: ls
        """
        try:
            handles = self.client.get_all_torrents()
            
            if not handles:
                print("No hay torrents activos")
                return
            
            # Preparar datos para tabla
            data = []
            for handle in handles:
                status = self.client.get_status(handle)
                data.append([
                    handle[:8] + "...",
                    status.file_name[:30],
                    f"{status.progress:.1f}%",
                    f"{status.downloaded_size:.1f} MB",
                    f"{status.file_size:.1f} MB",
                    status.peers,
                ])
            
            # Imprimir tabla
            headers = ["Handle", "Nombre", "Progreso", "Descargado", "Tamaño", "Peers"]
            print("\n" + tabulate(data, headers=headers, tablefmt="grid"))
            print(f"\nTotal: {len(handles)} torrent(s)")
            
        except Exception as e:
            print(f"✗ Error listando torrents: {e}")
            logger.error(f"Error en list: {e}", exc_info=True)
    
    def do_ls(self, arg):
        """Alias de 'list'"""
        self.do_list(arg)
    
    def do_info(self, arg):
        """
        Muestra información detallada de un torrent.
        
        Uso: info <handle>
        Ejemplo: info a1b2c3d4
        """
        if not arg:
            print("✗ Error: Debes especificar el handle del torrent")
            print("Uso: info <handle>")
            return
        
        try:
            handle = arg.strip()
            
            # Buscar handle completo (permite prefijos)
            handles = self.client.get_all_torrents()
            matching = [h for h in handles if h.startswith(handle)]
            
            if not matching:
                print(f"✗ Error: Torrent no encontrado: {handle}")
                return
            
            if len(matching) > 1:
                print(f"✗ Error: Handle ambiguo. Coincidencias:")
                for h in matching:
                    print(f"  • {h[:8]}...")
                return
            
            full_handle = matching[0]
            status = self.client.get_status(full_handle)
            
            print(f"""
Información del torrent:
  • Handle: {full_handle}
  • Nombre: {status.file_name}
  • Tamaño total: {status.file_size:.2f} MB
  • Descargado: {status.downloaded_size:.2f} MB
  • Progreso: {status.progress:.1f}%
  • Chunks totales: {int(status.total_chunks)}
  • Peers activos: {status.peers}
  • Download rate: {status.download_rate:.2f} KB/s
  • Upload rate: {status.upload_rate:.2f} KB/s
""")
            
        except Exception as e:
            print(f"✗ Error obteniendo info: {e}")
            logger.error(f"Error en info: {e}", exc_info=True)
    
    def do_pause(self, arg):
        """
        Pausa la descarga de un torrent.
        
        Uso: pause <handle>
        Ejemplo: pause a1b2c3d4
        """
        if not arg:
            print("✗ Error: Debes especificar el handle del torrent")
            print("Uso: pause <handle>")
            return
        
        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            
            self.client.pause_torrent(handle)
            print(f"✓ Torrent pausado: {handle[:8]}...")
            
        except Exception as e:
            print(f"✗ Error pausando torrent: {e}")
            logger.error(f"Error en pause: {e}", exc_info=True)
    
    def do_resume(self, arg):
        """
        Reanuda la descarga de un torrent pausado.
        
        Uso: resume <handle>
        Ejemplo: resume a1b2c3d4
        """
        if not arg:
            print("✗ Error: Debes especificar el handle del torrent")
            print("Uso: resume <handle>")
            return
        
        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            
            self.client.resume_torrent(handle)
            print(f"✓ Torrent reanudado: {handle[:8]}...")
            
        except Exception as e:
            print(f"✗ Error reanudando torrent: {e}")
            logger.error(f"Error en resume: {e}", exc_info=True)
    
    def do_remove(self, arg):
        """
        Elimina un torrent (NO elimina el archivo descargado).
        
        Uso: remove <handle>
        Alias: rm, delete
        Ejemplo: remove a1b2c3d4
        """
        if not arg:
            print("✗ Error: Debes especificar el handle del torrent")
            print("Uso: remove <handle>")
            return
        
        try:
            handle = self._resolve_handle(arg.strip())
            if not handle:
                return
            
            status = self.client.get_status(handle)
            print(f"¿Eliminar torrent '{status.file_name}'? (s/n): ", end="")
            confirm = input().strip().lower()
            
            if confirm != 's':
                print("✗ Operación cancelada")
                return
            
            self.client.remove_torrent(handle)
            print(f"✓ Torrent eliminado: {handle[:8]}...")
            
        except Exception as e:
            print(f"✗ Error eliminando torrent: {e}")
            logger.error(f"Error en remove: {e}", exc_info=True)
    
    def do_rm(self, arg):
        """Alias de 'remove'"""
        self.do_remove(arg)
    
    def do_delete(self, arg):
        """Alias de 'remove'"""
        self.do_remove(arg)
    
    # ==================== Comandos de Creación ====================
    
    def do_create(self, arg):
        """
        Crea un nuevo archivo .p2p a partir de un archivo existente.
        
        Uso: create <archivo_origen>
        Ejemplo: create /path/to/large_file.bin
        """
        if not arg:
            print("✗ Error: Debes especificar el archivo origen")
            print("Uso: create <archivo_origen>")
            return
        
        try:
            file_path = Path(arg.strip())
            
            if not file_path.exists():
                print(f"✗ Error: Archivo no encontrado: {file_path}")
                return
            
            if not file_path.is_file():
                print(f"✗ Error: No es un archivo: {file_path}")
                return
            
            print(f"""
Crear torrent para:
  • Archivo: {file_path.name}
  • Tamaño: {file_path.stat().st_size / (1024*1024):.2f} MB
  • Ruta: {file_path}
""")
            
            # TODO: Implementar creación de torrent
            # Por ahora mock
            print("⚠ Función create_torrent() pendiente de implementar")
            print("  Debe generar archivo .p2p con:")
            print("  - info_hash (SHA256 del archivo)")
            print("  - file_name, file_size")
            print("  - chunk_size (16KB), total_chunks")
            print("  - metadata adicional")
            
        except Exception as e:
            print(f"✗ Error creando torrent: {e}")
            logger.error(f"Error en create: {e}", exc_info=True)
    
    # ==================== Comandos de Monitoreo ====================
    
    def do_watch(self, arg):
        """
        Monitorea el progreso de torrents en tiempo real.
        
        Uso: watch [handle]
        Si no se especifica handle, muestra todos los torrents.
        Presiona Ctrl+C para detener.
        
        Ejemplo: watch
        Ejemplo: watch a1b2c3d4
        """
        try:
            target_handle = None
            if arg:
                target_handle = self._resolve_handle(arg.strip())
                if not target_handle:
                    return
            
            print("Monitoreando torrents (Ctrl+C para detener)...\n")
            
            while True:
                # Limpiar pantalla (compatible con Unix y Windows)
                print("\033[2J\033[H", end="")
                
                handles = self.client.get_all_torrents()
                
                if target_handle:
                    handles = [h for h in handles if h == target_handle]
                
                if not handles:
                    print("No hay torrents para monitorear")
                    break
                
                # Preparar datos
                data = []
                for handle in handles:
                    status = self.client.get_status(handle)
                    
                    # Barra de progreso
                    bar_width = 20
                    filled = int(bar_width * status.progress / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    
                    data.append([
                        handle[:8] + "...",
                        status.file_name[:25],
                        bar,
                        f"{status.progress:.1f}%",
                        f"{status.downloaded_size:.1f}/{status.file_size:.1f} MB",
                        status.peers,
                    ])
                
                # Imprimir tabla
                headers = ["Handle", "Nombre", "Progreso", "%", "MB", "Peers"]
                print(tabulate(data, headers=headers, tablefmt="grid"))
                print(f"\nActualizado: {time.strftime('%H:%M:%S')}")
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\n✓ Monitoreo detenido")
        except Exception as e:
            print(f"\n✗ Error en monitoreo: {e}")
            logger.error(f"Error en watch: {e}", exc_info=True)
    
    # ==================== Comandos de Configuración ====================
    
    def do_config(self, arg):
        """
        Muestra o modifica la configuración del cliente.
        
        Uso: 
          config                    - Muestra configuración actual
          config set <key> <value>  - Modifica un valor
          
        Keys disponibles:
          download_path    - Carpeta de descargas
          torrent_path     - Carpeta de archivos .p2p
          listen_port      - Puerto de escucha P2P
          tracker_host     - IP del tracker principal
          tracker_port     - Puerto del tracker principal
        
        Ejemplo: config set listen_port 6881
        Ejemplo: config set download_path /home/user/downloads
        """
        args = arg.split()
        
        if not args:
            # Mostrar config actual
            self._print_config_summary()
            return
        
        if args[0] == "set" and len(args) >= 3:
            key = args[1]
            value = " ".join(args[2:])
            
            try:
                if key == "download_path":
                    self.config.set("General", "download_path", value)
                elif key == "torrent_path":
                    self.config.set("General", "torrent_path", value)
                elif key == "listen_port":
                    self.config.set("General", "listen_port", value)
                elif key in ["tracker_host", "tracker_port"]:
                    # Tracker address se guarda como "host:port"
                    current_host, current_port = self.config.get_tracker_address()
                    if key == "tracker_host":
                        new_address = f"{value}:{current_port}"
                    else:
                        new_address = f"{current_host}:{value}"
                    self.config.set("General", "tracker_address", new_address)
                else:
                    print(f"✗ Error: Key desconocido: {key}")
                    return
                
                print(f"✓ Configuración actualizada: {key} = {value}")
                print("⚠ Reinicia el cliente para aplicar cambios")
                
            except Exception as e:
                print(f"✗ Error modificando configuración: {e}")
        else:
            print("✗ Uso: config set <key> <value>")
    
    def do_restart(self, arg):
        """
        Reinicia el cliente (aplica cambios de configuración).
        
        Uso: restart
        """
        try:
            print("Reiniciando cliente...")
            
            if self.client:
                self.client.stop()
            
            self._init_client()
            print("✓ Cliente reiniciado")
            
        except Exception as e:
            print(f"✗ Error reiniciando cliente: {e}")
            logger.error(f"Error en restart: {e}", exc_info=True)
    
    # ==================== Comandos de Debug ====================
    
    def do_connect(self, arg):
        """
        Conecta manualmente a un peer (debug/testing).
        
        Uso: connect <host> <port>
        Ejemplo: connect 192.168.1.100 6881
        """
        args = arg.split()
        
        if len(args) != 2:
            print("✗ Error: Formato incorrecto")
            print("Uso: connect <host> <port>")
            return
        
        try:
            host = args[0]
            port = int(args[1])
            
            result = self.client.connect_to_peer(host, port)
            
            if result:
                print(f"✓ Conectado a peer {host}:{port}")
            else:
                print(f"✗ Error conectando a peer {host}:{port}")
                
        except ValueError:
            print("✗ Error: Puerto debe ser numérico")
        except Exception as e:
            print(f"✗ Error conectando: {e}")
            logger.error(f"Error en connect: {e}", exc_info=True)
    
    def do_debug(self, arg):
        """
        Muestra información de debug del cliente.
        
        Uso: debug
        """
        try:
            print("=== Debug Info ===")
            print(f"Cliente inicializado: {self._running}")
            print(f"Peer ID: {self.client.client_manager.peer_id}")
            
            if self.client.client_manager:
                print(f"Event loop activo: {self.client.client_manager._loop is not None}")
                print(f"Event loop thread: {self.client.client_manager._loop_thread}")
                print(f"Torrents activos: {len(self.client.client_manager._torrents)}")
                print(f"Descargas activas: {len(self.client.client_manager._download_tasks)}")
            
            print("\n=== Servicios ===")
            if self.client.client_manager.peer_service:
                ps = self.client.client_manager.peer_service
                print(f"PeerService host: {ps.host}:{ps.port}")
                print(f"Torrents compartidos: {len(ps._shared_torrents)}")
            
            if self.client.client_manager.tracker_manager:
                tm = self.client.client_manager.tracker_manager
                print(f"Trackers conocidos: {len(tm._known_trackers)}")
                print(f"Tracker actual: {tm._known_trackers[tm._current_tracker_idx] if tm._known_trackers else 'N/A'}")
            
        except Exception as e:
            print(f"✗ Error obteniendo debug info: {e}")
            logger.error(f"Error en debug: {e}", exc_info=True)
    
    # ==================== Comandos de Sistema ====================
    
    def do_exit(self, arg):
        """
        Sale del CLI y detiene el cliente.
        
        Uso: exit
        Alias: quit, q
        """
        print("\nDeteniendo cliente...")
        
        if self.client:
            try:
                self.client.stop()
                print("✓ Cliente detenido")
            except Exception as e:
                print(f"⚠ Error deteniendo cliente: {e}")
        
        print("Hasta luego!")
        return True
    
    def do_quit(self, arg):
        """Alias de 'exit'"""
        return self.do_exit(arg)
    
    def do_q(self, arg):
        """Alias de 'exit'"""
        return self.do_exit(arg)
    
    def do_clear(self, arg):
        """
        Limpia la pantalla.
        
        Uso: clear
        Alias: cls
        """
        print("\033[2J\033[H", end="")
    
    def do_cls(self, arg):
        """Alias de 'clear'"""
        self.do_clear(arg)
    
    # ==================== Utilidades ====================
    
    def _resolve_handle(self, prefix: str) -> Optional[str]:
        """Resuelve un prefijo de handle al handle completo"""
        handles = self.client.get_all_torrents()
        matching = [h for h in handles if h.startswith(prefix)]
        
        if not matching:
            print(f"✗ Error: Torrent no encontrado: {prefix}")
            return None
        
        if len(matching) > 1:
            print(f"✗ Error: Handle ambiguo. Coincidencias:")
            for h in matching:
                print(f"  • {h[:8]}...")
            return None
        
        return matching[0]
    
    def emptyline(self):
        """No hacer nada en línea vacía"""
        pass
    
    def default(self, line):
        """Comando no reconocido"""
        print(f"✗ Comando no reconocido: {line}")
        print("Escribe 'help' para ver comandos disponibles")


def main():
    """Entry point del CLI"""
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bittorrent_cli.log'),
            # No logging a stdout para no interferir con CLI
        ]
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
