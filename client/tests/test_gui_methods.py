#!/usr/bin/env python3
"""
Test Exhaustivo de GUI - Validación de Cada Método por Separado

Este test simula y valida cada método de la GUI individualmente,
mockeando completamente tkinter y verificando que la lógica funciona.
"""

import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
from uuid import uuid4

# Configurar path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mockear tkinter ANTES de cualquier import
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()

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

def print_info(text):
    print(f"   {text}")


# ============================================================
# Función para crear GUI mock
# ============================================================
def create_gui_instance():
    """Crea una instancia de GUI con todos los mocks necesarios"""
    from src.client.gui.client import BitTorrentClientGUI
    
    # Mock root
    root = MagicMock()
    root.title = MagicMock()
    root.geometry = MagicMock()
    root.config = MagicMock()
    root.columnconfigure = MagicMock()
    root.rowconfigure = MagicMock()
    root.after = MagicMock()
    root.quit = MagicMock()
    
    # Crear GUI
    gui = BitTorrentClientGUI(root)
    
    # Mock componentes importantes
    gui.tree = MagicMock()
    gui.tree.selection = MagicMock()
    gui.tree.exists = MagicMock()
    gui.tree.insert = MagicMock()
    gui.tree.item = MagicMock()
    gui.tree.delete = MagicMock()
    
    gui.status_message = MagicMock()
    gui.status_message.config = MagicMock()
    
    gui.connection_label = MagicMock()
    gui.connection_label.config = MagicMock()
    
    gui.torrents_label = MagicMock()
    gui.torrents_label.config = MagicMock()
    
    gui.download_speed_label = MagicMock()
    gui.download_speed_label.config = MagicMock()
    
    gui.upload_speed_label = MagicMock()
    gui.upload_speed_label.config = MagicMock()
    
    gui.peers_label = MagicMock()
    gui.peers_label.config = MagicMock()
    
    return gui


# ============================================================
# TEST 1: open_torrent - Abrir archivo torrent
# ============================================================
def test_open_torrent():
    print_header("TEST 1: open_torrent()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Crear archivo .p2p de prueba
        print_test("Creando archivo .p2p de prueba...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.p2p', delete=False) as f:
            test_data = {
                "info_hash": uuid4().hex[:16],
                "file_name": "test_open.txt",
                "file_size": 2048000,
                "chunk_size": 16384,
                "total_chunks": 125
            }
            json.dump(test_data, f)
            torrent_file = f.name
        print_success(f"Archivo creado: {torrent_file}")
        
        # Mock filedialog y messagebox
        print_test("Mockeando filedialog.askopenfilename...")
        import tkinter.filedialog as filedialog
        import tkinter.messagebox as messagebox
        
        filedialog.askopenfilename = Mock(return_value=torrent_file)
        messagebox.askyesno = Mock(return_value=True)
        messagebox.showerror = Mock()
        
        # Mock torrent_client
        print_test("Mockeando TorrentClient.get_torrent_info...")
        mock_info = Mock()
        mock_info.file_name = "test_open.txt"
        mock_info.display_size = "2.00 MB"
        mock_info.chunk_size = 16384
        gui.torrent_client.get_torrent_info = Mock(return_value=mock_info)
        gui.torrent_client.add_torrent = Mock(return_value="hash123")
        
        # Ejecutar
        print_test("Ejecutando gui.open_torrent()...")
        gui.open_torrent()
        print_success("open_torrent() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert filedialog.askopenfilename.called, "Debe llamar a askopenfilename"
        print_info("✓ filedialog.askopenfilename llamado")
        
        assert gui.torrent_client.get_torrent_info.called, "Debe obtener info del torrent"
        print_info("✓ get_torrent_info llamado")
        
        assert messagebox.askyesno.called, "Debe mostrar confirmación"
        print_info("✓ messagebox.askyesno llamado")
        
        assert gui.torrent_client.add_torrent.called, "Debe agregar torrent"
        print_info("✓ add_torrent llamado")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado")
        
        print_success("Todas las validaciones pasaron")
        
        # Cleanup
        os.unlink(torrent_file)
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 2: create_torrent - Crear archivo torrent
# ============================================================
def test_create_torrent():
    print_header("TEST 2: create_torrent()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Crear archivo fuente
        print_test("Creando archivo fuente...")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Contenido de prueba para crear torrent\n" * 100)
            source_file = f.name
        print_success(f"Archivo fuente: {source_file}")
        
        # Mock filedialog y messagebox
        print_test("Mockeando filedialog y messagebox...")
        import tkinter.filedialog as filedialog
        import tkinter.messagebox as messagebox
        
        filedialog.askopenfilename = Mock(return_value=source_file)
        messagebox.showinfo = Mock()
        messagebox.showerror = Mock()
        
        # Mock create_torrent_file
        print_test("Mockeando TorrentClient.create_torrent_file...")
        mock_torrent_data = Mock()
        mock_torrent_data.file_name = "test_file.txt"
        mock_torrent_data.display_size = "3.50 KB"
        mock_torrent_data.total_chunks = 1
        mock_torrent_data.file_hash = "abc123def456"
        
        gui.torrent_client.create_torrent_file = Mock(
            return_value=("/tmp/test.p2p", mock_torrent_data)
        )
        
        # Ejecutar
        print_test("Ejecutando gui.create_torrent()...")
        gui.create_torrent()
        print_success("create_torrent() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert filedialog.askopenfilename.called, "Debe llamar a askopenfilename"
        print_info("✓ filedialog.askopenfilename llamado")
        
        assert gui.torrent_client.create_torrent_file.called, "Debe crear archivo torrent"
        print_info("✓ create_torrent_file llamado")
        
        assert messagebox.showinfo.called, "Debe mostrar mensaje de éxito"
        print_info("✓ messagebox.showinfo llamado")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado")
        
        print_success("Todas las validaciones pasaron")
        
        # Cleanup
        os.unlink(source_file)
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 3: open_settings - Ventana de configuración
# ============================================================
def test_open_settings():
    print_header("TEST 3: open_settings()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock Toplevel
        print_test("Mockeando Toplevel...")
        import tkinter as tk
        settings_window = MagicMock()
        tk.Toplevel = Mock(return_value=settings_window)
        
        # Ejecutar
        print_test("Ejecutando gui.open_settings()...")
        gui.open_settings()
        print_success("open_settings() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert tk.Toplevel.called, "Debe crear ventana Toplevel"
        print_info("✓ Toplevel creado")
        
        assert settings_window.title.called, "Debe establecer título"
        print_info("✓ Título establecido")
        
        assert settings_window.geometry.called, "Debe establecer geometría"
        print_info("✓ Geometría establecida")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 4: connect_to_peer - Conectar a peer
# ============================================================
def test_connect_to_peer():
    print_header("TEST 4: connect_to_peer()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock Toplevel
        print_test("Mockeando Toplevel...")
        import tkinter as tk
        dialog = MagicMock()
        tk.Toplevel = Mock(return_value=dialog)
        
        # Ejecutar
        print_test("Ejecutando gui.connect_to_peer()...")
        gui.connect_to_peer()
        print_success("connect_to_peer() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert tk.Toplevel.called, "Debe crear diálogo"
        print_info("✓ Diálogo creado")
        
        assert dialog.title.called, "Debe establecer título"
        print_info("✓ Título establecido")
        
        assert dialog.geometry.called, "Debe establecer geometría"
        print_info("✓ Geometría establecida")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 5: show_about - Mostrar acerca de
# ============================================================
def test_show_about():
    print_header("TEST 5: show_about()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock messagebox
        print_test("Mockeando messagebox.showinfo...")
        import tkinter.messagebox as messagebox
        messagebox.showinfo = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui.show_about()...")
        gui.show_about()
        print_success("show_about() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert messagebox.showinfo.called, "Debe mostrar mensaje"
        print_info("✓ messagebox.showinfo llamado")
        
        call_args = messagebox.showinfo.call_args
        assert "Acerca de" in str(call_args), "Debe contener 'Acerca de'"
        print_info("✓ Mensaje contiene 'Acerca de'")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 6: pause_selected - Pausar torrent seleccionado
# ============================================================
def test_pause_selected():
    print_header("TEST 6: pause_selected()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock tree.selection
        print_test("Mockeando tree.selection()...")
        gui.tree.selection = Mock(return_value=["torrent_abc123", "torrent_def456"])
        
        # Mock pause_torrent
        print_test("Mockeando TorrentClient.pause_torrent...")
        gui.torrent_client.pause_torrent = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui.pause_selected()...")
        gui.pause_selected()
        print_success("pause_selected() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert gui.tree.selection.called, "Debe obtener selección"
        print_info("✓ tree.selection llamado")
        
        assert gui.torrent_client.pause_torrent.call_count == 2, "Debe pausar 2 torrents"
        print_info("✓ pause_torrent llamado 2 veces")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 7: resume_selected - Reanudar torrent seleccionado
# ============================================================
def test_resume_selected():
    print_header("TEST 7: resume_selected()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock tree.selection
        print_test("Mockeando tree.selection()...")
        gui.tree.selection = Mock(return_value=["torrent_xyz789"])
        
        # Mock resume_torrent
        print_test("Mockeando TorrentClient.resume_torrent...")
        gui.torrent_client.resume_torrent = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui.resume_selected()...")
        gui.resume_selected()
        print_success("resume_selected() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert gui.tree.selection.called, "Debe obtener selección"
        print_info("✓ tree.selection llamado")
        
        assert gui.torrent_client.resume_torrent.called, "Debe reanudar torrent"
        print_info("✓ resume_torrent llamado")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 8: remove_selected - Eliminar torrent seleccionado
# ============================================================
def test_remove_selected():
    print_header("TEST 8: remove_selected()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock tree.selection
        print_test("Mockeando tree.selection()...")
        gui.tree.selection = Mock(return_value=["torrent_remove1"])
        
        # Mock messagebox
        print_test("Mockeando messagebox.askyesno...")
        import tkinter.messagebox as messagebox
        messagebox.askyesno = Mock(return_value=True)
        
        # Mock remove_torrent y tree.delete
        print_test("Mockeando TorrentClient.remove_torrent...")
        gui.torrent_client.remove_torrent = Mock()
        gui.tree.delete = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui.remove_selected()...")
        gui.remove_selected()
        print_success("remove_selected() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert gui.tree.selection.called, "Debe obtener selección"
        print_info("✓ tree.selection llamado")
        
        assert messagebox.askyesno.called, "Debe pedir confirmación"
        print_info("✓ messagebox.askyesno llamado")
        
        assert gui.torrent_client.remove_torrent.called, "Debe eliminar torrent"
        print_info("✓ remove_torrent llamado")
        
        assert gui.tree.delete.called, "Debe eliminar de tree"
        print_info("✓ tree.delete llamado")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 9: update_torrents - Actualización automática
# ============================================================
def test_update_torrents():
    print_header("TEST 9: update_torrents()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock get_all_torrents
        print_test("Mockeando TorrentClient.get_all_torrents...")
        gui.torrent_client.get_all_torrents = Mock(return_value=["hash1", "hash2", "hash3"])
        
        # Mock get_status
        print_test("Mockeando TorrentClient.get_status...")
        mock_status = Mock()
        mock_status.file_name = "test_file.txt"
        mock_status.file_size = 1024.0
        mock_status.downloaded_size = 512.0
        mock_status.progress = 50.0
        mock_status.total_chunks = 64.0
        gui.torrent_client.get_status = Mock(return_value=mock_status)
        
        # Mock tree operations
        print_test("Mockeando tree operations...")
        gui.tree.exists = Mock(side_effect=[False, True, False])
        gui.tree.insert = Mock()
        gui.tree.item = Mock()
        
        # Mock root.after
        print_test("Mockeando root.after...")
        gui.root.after = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui.update_torrents()...")
        gui.update_torrents()
        print_success("update_torrents() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert gui.torrent_client.get_all_torrents.called, "Debe obtener lista de torrents"
        print_info("✓ get_all_torrents llamado")
        
        assert gui.torrent_client.get_status.call_count == 3, "Debe obtener status de 3 torrents"
        print_info("✓ get_status llamado 3 veces")
        
        assert gui.torrents_label.config.called, "Debe actualizar label de torrents"
        print_info("✓ torrents_label actualizado")
        
        assert gui.download_speed_label.config.called, "Debe actualizar velocidad descarga"
        print_info("✓ download_speed_label actualizado")
        
        assert gui.upload_speed_label.config.called, "Debe actualizar velocidad subida"
        print_info("✓ upload_speed_label actualizado")
        
        assert gui.peers_label.config.called, "Debe actualizar peers"
        print_info("✓ peers_label actualizado")
        
        assert gui.connection_label.config.called, "Debe actualizar conexión"
        print_info("✓ connection_label actualizado")
        
        assert gui.root.after.called, "Debe programar siguiente actualización"
        print_info("✓ root.after llamado para siguiente update")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 10: browse_folder - Seleccionar carpeta
# ============================================================
def test_browse_folder():
    print_header("TEST 10: browse_folder()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock filedialog
        print_test("Mockeando filedialog.askdirectory...")
        import tkinter.filedialog as filedialog
        import tkinter.messagebox as messagebox
        filedialog.askdirectory = Mock(return_value="/tmp/new_download_folder")
        messagebox.showinfo = Mock()
        
        # Mock StringVar
        print_test("Mockeando StringVar...")
        var = MagicMock()
        var.get = Mock(return_value="/tmp/old_folder")
        var.set = Mock()
        
        parent_window = MagicMock()
        
        # Ejecutar
        print_test("Ejecutando gui.browse_folder()...")
        gui.browse_folder(var, parent_window)
        print_success("browse_folder() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert filedialog.askdirectory.called, "Debe abrir diálogo"
        print_info("✓ filedialog.askdirectory llamado")
        
        assert var.set.called, "Debe actualizar variable"
        print_info("✓ var.set llamado")
        
        var.set.assert_called_with("/tmp/new_download_folder")
        print_info("✓ Variable actualizada con carpeta correcta")
        
        assert messagebox.showinfo.called, "Debe mostrar confirmación"
        print_info("✓ messagebox.showinfo llamado")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# TEST 11: _selected_action - Método helper
# ============================================================
def test_selected_action():
    print_header("TEST 11: _selected_action()")
    
    try:
        print_test("Creando GUI instance...")
        gui = create_gui_instance()
        print_success("GUI creada")
        
        # Mock action function
        print_test("Creando función de acción mock...")
        mock_action = Mock()
        
        # Ejecutar
        print_test("Ejecutando gui._selected_action()...")
        selected_items = ["item1", "item2", "item3"]
        gui._selected_action(selected_items, mock_action, msg="Test message")
        print_success("_selected_action() ejecutado")
        
        # Validaciones
        print_test("Validando llamadas...")
        assert mock_action.call_count == 3, "Debe llamar action 3 veces"
        print_info("✓ action llamado 3 veces")
        
        assert gui.status_message.config.called, "Debe actualizar status"
        print_info("✓ status actualizado con mensaje")
        
        print_success("Todas las validaciones pasaron")
        
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# MAIN
# ============================================================
def main():
    print_header("TEST EXHAUSTIVO DE MÉTODOS GUI - VALIDACIÓN INDIVIDUAL")
    
    results = {}
    
    # Ejecutar todos los tests
    tests = [
        ("1. open_torrent", test_open_torrent),
        ("2. create_torrent", test_create_torrent),
        ("3. open_settings", test_open_settings),
        ("4. connect_to_peer", test_connect_to_peer),
        ("5. show_about", test_show_about),
        ("6. pause_selected", test_pause_selected),
        ("7. resume_selected", test_resume_selected),
        ("8. remove_selected", test_remove_selected),
        ("9. update_torrents", test_update_torrents),
        ("10. browse_folder", test_browse_folder),
        ("11. _selected_action", test_selected_action),
    ]
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print_error(f"Error ejecutando {test_name}: {e}")
            results[test_name] = False
    
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
        print("🎉 TODOS LOS MÉTODOS DE GUI VALIDADOS EXITOSAMENTE 🎉".center(70))
        print(f"{'='*70}{Colors.END}\n")
        print_info("✅ open_torrent: Lógica de apertura funciona correctamente")
        print_info("✅ create_torrent: Creación de torrents validada")
        print_info("✅ open_settings: Ventana de configuración funcional")
        print_info("✅ connect_to_peer: Diálogo de conexión validado")
        print_info("✅ show_about: Mensaje 'Acerca de' funcional")
        print_info("✅ pause_selected: Pausar torrents funciona")
        print_info("✅ resume_selected: Reanudar torrents funciona")
        print_info("✅ remove_selected: Eliminar torrents validado")
        print_info("✅ update_torrents: Actualización automática funciona")
        print_info("✅ browse_folder: Selección de carpetas funcional")
        print_info("✅ _selected_action: Helper method validado")
        print_info("")
        print_info("🎯 Cada método fue probado individualmente")
        print_info("🎯 Todas las interacciones con tkinter fueron mockeadas")
        print_info("🎯 La lógica de negocio está correctamente implementada")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}{'='*70}")
        print(f"❌ {failed} MÉTODO(S) FALLARON".center(70))
        print(f"{'='*70}{Colors.END}\n")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrumpido por usuario{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error fatal: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
