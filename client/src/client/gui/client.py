import os
import logging
import humanize
import asyncio
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from datetime import datetime
from typing import Optional
from ..config.config_mng import ConfigManager
from ..core.torrent_client import TorrentClient

logger = logging.getLogger(__name__)


class BitTorrentClientGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cliente BitTorrent")
        self.root.geometry("900x600")

        self.config_manager = ConfigManager()
        self.torrent_client = TorrentClient(self.config_manager)

        # Reducir ruido de logs de discovery/conexiones internas
        logging.getLogger("bit_lib.services.discovery").setLevel(logging.WARNING)
        logging.getLogger("bit_lib.services._client").setLevel(logging.WARNING)

        # Discovery service (opcional)
        self._discovery_enabled = self._get_bool_config(
            "tracker_discovery_enabled", True
        )
        self._last_discovery = None
        self._discovery_interval = self._get_int_config(
            "tracker_discovery_interval", 60
        )
        self._discovery_running = False  # Flag para evitar ejecuciones concurrentes

        # Health-check periódico de trackers
        self._tracker_health_interval = self._get_int_config(
            "tracker_health_interval", 30
        )
        self._last_tracker_health = None
        self._tracker_health_running = False

        self.setup_menu()
        self.setup_ui()

        # Inicializar TrackerManager al inicio para que el label se actualice
        self._init_tracker_manager()

        self.update_torrents()

    def _get_int_config(self, key: str, default: int) -> int:
        raw = self.config_manager.get("General", key)
        if not raw:
            return default
        try:
            value = int(raw)
            return value if value > 0 else default
        except ValueError:
            return default

    def _get_bool_config(self, key: str, default: bool) -> bool:
        raw = self.config_manager.get("General", key)
        if not raw:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}

    def _get_expected_tracker_hosts(self) -> list[str]:
        """Retorna hosts esperados de trackers a partir del principal (tracker-1..4)."""
        host, _ = self.config_manager.get_tracker_address()
        if host.startswith("tracker-"):
            return [f"tracker-{i}" for i in range(1, 5)]
        return [host]

    def _init_tracker_manager(self):
        """Inicializa servicios usando el event loop persistente de TorrentClient"""
        # Evitar crear loops temporales: TrackerClient debe vivir en el mismo
        # loop persistente que usa TorrentClient para descargas y announce.
        if not self.torrent_client._initialized:
            self.torrent_client.setup_session()
        else:
            self.torrent_client._run_async_in_thread(
                self.torrent_client.tracker_manager.start()
            )

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Abrir Torrent (.p2p)", command=self.open_torrent)
        file_menu.add_command(label="Crear Torrent", command=self.create_torrent)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Conectar a Peer", command=self.connect_to_peer)
        tools_menu.add_command(label="Configuración", command=self.open_settings)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self.show_about)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(toolbar, text="Agregar Torrent", command=self.open_torrent).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(toolbar, text="Pausar", command=self.pause_selected).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(toolbar, text="Reanudar", command=self.resume_selected).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(toolbar, text="Eliminar", command=self.remove_selected).pack(
            side=tk.LEFT, padx=5
        )

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = (
            "Nombre",
            "Estado",
            "Tamaño",
            "Descargado",
            "Progreso",
            "Peers",
            "DL",
            "UL",
            "ETA",
            "Chunks",
        )
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self._tree_columns = columns

        self._tree_headers = {
            "Nombre": "Archivo",
            "Estado": "Estado",
            "Tamaño": "Tamaño (bytes)",
            "Descargado": "Descargado",
            "Progreso": "Progreso (%)",
            "Peers": "Peers",
            "DL": "DL",
            "UL": "UL",
            "ETA": "ETA",
            "Chunks": "Chunks",
        }

        self.tree.heading("Nombre", text=self._tree_headers["Nombre"])
        self.tree.heading("Estado", text=self._tree_headers["Estado"])
        self.tree.heading("Tamaño", text=self._tree_headers["Tamaño"])
        self.tree.heading("Descargado", text=self._tree_headers["Descargado"])
        self.tree.heading("Progreso", text=self._tree_headers["Progreso"])
        self.tree.heading("Peers", text=self._tree_headers["Peers"])
        self.tree.heading("DL", text=self._tree_headers["DL"])
        self.tree.heading("UL", text=self._tree_headers["UL"])
        self.tree.heading("ETA", text=self._tree_headers["ETA"])
        self.tree.heading("Chunks", text=self._tree_headers["Chunks"])

        # ✅ Usar width fijo en lugar de stretch para evitar cambios dinámicos
        self.tree.column("Nombre", width=250, stretch=False)
        self.tree.column("Estado", width=120, stretch=False)
        self.tree.column("Tamaño", width=100, anchor=tk.E, stretch=False)
        self.tree.column("Descargado", width=100, anchor=tk.E, stretch=False)
        self.tree.column("Progreso", width=100, anchor=tk.E, stretch=False)
        self.tree.column("Peers", width=60, anchor=tk.E, stretch=False)
        self.tree.column("DL", width=90, anchor=tk.E, stretch=False)
        self.tree.column("UL", width=90, anchor=tk.E, stretch=False)
        self.tree.column("ETA", width=90, anchor=tk.E, stretch=False)
        self.tree.column("Chunks", width=100, anchor=tk.E, stretch=False)
        self._fit_tree_columns_to_headers()

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        h_scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        trackers_frame = ttk.LabelFrame(main_frame, text="Trackers", padding="6")
        trackers_frame.grid(row=2, column=0, sticky="ew", pady=(8, 4))
        trackers_frame.columnconfigure(0, weight=1)

        tracker_columns = ("Tracker", "Estado", "Latencia", "Último check")
        self.trackers_tree = ttk.Treeview(
            trackers_frame,
            columns=tracker_columns,
            show="headings",
            height=4,
        )
        self.trackers_tree.heading("Tracker", text="Tracker")
        self.trackers_tree.heading("Estado", text="Estado")
        self.trackers_tree.heading("Latencia", text="Latencia")
        self.trackers_tree.heading("Último check", text="Último check")

        self.trackers_tree.column("Tracker", width=220, stretch=False)
        self.trackers_tree.column("Estado", width=130, stretch=False)
        self.trackers_tree.column("Latencia", width=100, anchor=tk.E, stretch=False)
        self.trackers_tree.column("Último check", width=130, stretch=False)
        self.trackers_tree.tag_configure("active", foreground="#16a34a")
        self.trackers_tree.tag_configure("checking", foreground="#d97706")
        self.trackers_tree.tag_configure("down", foreground="#dc2626")
        self.trackers_tree.grid(row=0, column=0, sticky="ew")

        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.grid(row=3, column=0, sticky="ew", pady=(6, 5))

        status_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=4, column=0, sticky="ew", pady=(5, 0))

        left_status_frame = ttk.Frame(status_frame)
        left_status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=3)

        # Label de tracker actual (único indicador de conexión)
        self.tracker_label = ttk.Label(
            left_status_frame, text="Tracker conectado a --", foreground="gray"
        )
        self.tracker_label.pack(side=tk.LEFT, padx=(0, 15))

        self.torrents_label = ttk.Label(left_status_frame, text="Torrents: 0")
        self.torrents_label.pack(side=tk.LEFT, padx=(0, 15))

        self.download_speed_label = ttk.Label(
            left_status_frame, text="Descarga: 0.0 KB/s"
        )
        self.download_speed_label.pack(side=tk.LEFT, padx=(0, 15))

        self.upload_speed_label = ttk.Label(left_status_frame, text="Subida: 0.0 KB/s")
        self.upload_speed_label.pack(side=tk.LEFT, padx=(0, 15))

        self.peers_label = ttk.Label(left_status_frame, text="Peers: 0")
        self.peers_label.pack(side=tk.LEFT)

        right_status_frame = ttk.Frame(status_frame)
        right_status_frame.pack(side=tk.RIGHT, padx=5, pady=3)

        self.status_message = ttk.Label(
            right_status_frame, text="Listo", foreground="gray"
        )
        self.status_message.pack(side=tk.RIGHT)

    def _fit_tree_columns_to_headers(self):
        heading_font = tkfont.nametofont("TkHeadingFont")
        min_width = {
            "Nombre": 250,
            "Estado": 120,
            "Tamaño": 110,
            "Descargado": 110,
            "Progreso": 110,
            "Peers": 70,
            "DL": 90,
            "UL": 90,
            "ETA": 90,
            "Chunks": 100,
        }

        for column in self._tree_columns:
            label = self._tree_headers.get(column, column)
            header_width = heading_font.measure(label) + 24
            width = max(min_width.get(column, 80), header_width)
            self.tree.column(column, width=width)

        self.tree.column("Nombre", stretch=False)

    def _on_tree_configure(self, event):
        """Handle tree resize event to prevent column collapse"""
        # Called whenever the tree widget is resized
        # Make sure columns don't collapse completely
        total_width = self.tree.winfo_width()
        if total_width > 1:  # Avoid processing invalid widths during initialization
            # Re-ensure minimum widths for columns
            min_widths = {
                "Nombre": 150,
                "Estado": 80,
                "Tamaño": 80,
                "Descargado": 80,
                "Progreso": 80,
                "Peers": 50,
                "DL": 70,
                "UL": 70,
                "ETA": 70,
                "Chunks": 70,
            }

            for column in self._tree_columns:
                current_width = self.tree.column(column, "width")
                min_width = min_widths.get(column, 70)
                # If column has been resized too small, restore minimum width
                if current_width < min_width:
                    self.tree.column(column, width=min_width)

    def open_torrent(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo torrent",
            filetypes=[
                ("Archivos P2P Torrent", "*.p2p"),
                ("Todos los archivos", "*.*"),
            ],
        )

        if filename:
            try:
                info = self.torrent_client.get_torrent_info(filename)
                name = info.file_name

                msg = f"Nombre: {name}\n"
                msg += f"Tamaño: {info.display_size}\n"
                msg += f"Archivos: {info.chunk_size}\n\n"
                msg += "¿Desea agregar este torrent?"

                if messagebox.askyesno("Información del Torrent", msg):
                    self.torrent_client.add_torrent(info)
                    self.status_message.config(text=f"Torrent agregado: {name}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar torrent: {str(e)}")

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configuración del Cliente")
        settings_window.geometry("700x650")
        settings_window.resizable(True, True)

        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")

        title_label = ttk.Label(
            main_frame,
            text="Configuración del Cliente BitTorrent",
            font=("TkDefaultFont", 12, "bold"),
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        separator1 = ttk.Separator(main_frame, orient="horizontal")
        separator1.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 15))

        general_label = ttk.Label(
            main_frame, text="General", font=("TkDefaultFont", 10, "bold")
        )
        general_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 10))

        # Carpeta de Descargas
        ttk.Label(main_frame, text="Carpeta de Descargas:").grid(
            row=3, column=0, sticky=tk.W, pady=8
        )
        download_path_var = tk.StringVar(
            value=self.config_manager.get("General", "download_path")
        )
        path_entry = ttk.Entry(main_frame, textvariable=download_path_var, width=45)
        path_entry.grid(row=3, column=1, pady=8, padx=(10, 5))
        browse_btn = ttk.Button(
            main_frame,
            text="Buscar",
            command=lambda: self.browse_folder(download_path_var, settings_window),
        )
        browse_btn.grid(row=3, column=2, padx=5)

        # Carpeta de Torrents
        ttk.Label(main_frame, text="Carpeta de Torrents (.p2p):").grid(
            row=4, column=0, sticky=tk.W, pady=8
        )
        torrent_path_var = tk.StringVar(
            value=self.config_manager.get("General", "torrent_path")
        )
        torrent_path_entry = ttk.Entry(
            main_frame, textvariable=torrent_path_var, width=45
        )
        torrent_path_entry.grid(row=4, column=1, pady=8, padx=(10, 5))
        browse_torrent_btn = ttk.Button(
            main_frame,
            text="Buscar",
            command=lambda: self.browse_folder(torrent_path_var, settings_window),
        )
        browse_torrent_btn.grid(row=4, column=2, padx=5)

        separator2 = ttk.Separator(main_frame, orient="horizontal")
        separator2.grid(row=5, column=0, columnspan=3, sticky="ew", pady=15)

        network_label = ttk.Label(
            main_frame, text="Red y Conexión", font=("TkDefaultFont", 10, "bold")
        )
        network_label.grid(row=6, column=0, sticky=tk.W, pady=(0, 10))

        # Puerto de Escucha
        ttk.Label(main_frame, text="Puerto de Escucha:").grid(
            row=7, column=0, sticky=tk.W, pady=8
        )
        port_var = tk.StringVar(
            value=str(self.config_manager.get("General", "listen_port"))
        )
        port_entry = ttk.Entry(main_frame, textvariable=port_var, width=45)
        port_entry.grid(
            row=7, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W
        )
        ttk.Label(
            main_frame, text="(Rango recomendado: 6881-6889)", foreground="gray"
        ).grid(row=8, column=1, sticky=tk.W, padx=(10, 0))

        # Dirección del Tracker
        ttk.Label(main_frame, text="Dirección del Tracker (ip:puerto):").grid(
            row=9, column=0, sticky=tk.W, pady=8
        )

        tracker_ip, tracker_port = self.config_manager.get_tracker_address()

        # Crea un subframe para los campos tracker_ip y tracker_port
        tracker_frame = ttk.Frame(main_frame)
        tracker_frame.grid(row=9, column=1, sticky=tk.W, padx=(10, 5), columnspan=2)

        ttk.Label(tracker_frame, text="IP:").pack(side=tk.LEFT, padx=(0, 2))
        tracker_ip_var = tk.StringVar(value=tracker_ip)
        tracker_ip_entry = ttk.Entry(
            tracker_frame, textvariable=tracker_ip_var, width=14
        )
        tracker_ip_entry.pack(side=tk.LEFT)

        tracker_port_var = tk.StringVar(value=tracker_port)
        ttk.Label(tracker_frame, text="Puerto:").pack(side=tk.LEFT, padx=(12, 2))
        tracker_port_entry = ttk.Entry(
            tracker_frame, textvariable=tracker_port_var, width=6
        )
        tracker_port_entry.pack(side=tk.LEFT)

        separator3 = ttk.Separator(main_frame, orient="horizontal")
        separator3.grid(row=10, column=0, columnspan=3, sticky="ew", pady=15)

        bandwidth_label = ttk.Label(
            main_frame, text="Ancho de Banda", font=("TkDefaultFont", 10, "bold")
        )
        bandwidth_label.grid(row=11, column=0, sticky=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text="Límite de Descarga (KB/s):").grid(
            row=12, column=0, sticky=tk.W, pady=8
        )
        download_limit_var = tk.StringVar(
            value=str(self.config_manager.get("General", "max_download_rate"))
        )
        dl_entry = ttk.Entry(main_frame, textvariable=download_limit_var, width=45)
        dl_entry.grid(row=12, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W)
        ttk.Label(main_frame, text="(0 = sin límite)", foreground="gray").grid(
            row=13, column=1, sticky=tk.W, padx=(10, 0)
        )

        ttk.Label(main_frame, text="Límite de Subida (KB/s):").grid(
            row=14, column=0, sticky=tk.W, pady=8
        )
        upload_limit_var = tk.StringVar(
            value=str(self.config_manager.get("General", "max_upload_rate"))
        )
        ul_entry = ttk.Entry(main_frame, textvariable=upload_limit_var, width=45)
        ul_entry.grid(row=14, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W)
        ttk.Label(main_frame, text="(0 = sin límite)", foreground="gray").grid(
            row=15, column=1, sticky=tk.W, padx=(10, 0)
        )

        separator4 = ttk.Separator(main_frame, orient="horizontal")
        separator4.grid(row=16, column=0, columnspan=3, sticky="ew", pady=15)

        advanced_label = ttk.Label(
            main_frame, text="Opciones Avanzadas", font=("TkDefaultFont", 10, "bold")
        )
        advanced_label.grid(row=17, column=0, sticky=tk.W, pady=(0, 10))

        ttk.Label(main_frame, text="Máx. Conexiones:").grid(
            row=18, column=0, sticky=tk.W, pady=8
        )
        max_connections_var = tk.StringVar(
            value=str(self.config_manager.get("General", "max_connections") or "50")
        )
        ttk.Entry(main_frame, textvariable=max_connections_var, width=45).grid(
            row=18, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W
        )

        ttk.Label(main_frame, text="Health-check de trackers (seg):").grid(
            row=19, column=0, sticky=tk.W, pady=8
        )
        tracker_health_var = tk.StringVar(value=str(self._tracker_health_interval))
        ttk.Entry(main_frame, textvariable=tracker_health_var, width=45).grid(
            row=19, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W
        )

        ttk.Label(main_frame, text="Discovery de trackers (seg):").grid(
            row=20, column=0, sticky=tk.W, pady=8
        )
        discovery_interval_var = tk.StringVar(value=str(self._discovery_interval))
        ttk.Entry(main_frame, textvariable=discovery_interval_var, width=45).grid(
            row=20, column=1, pady=8, padx=(10, 5), columnspan=2, sticky=tk.W
        )

        discovery_enabled_var = tk.BooleanVar(value=self._discovery_enabled)
        ttk.Checkbutton(
            main_frame,
            text="Habilitar discovery automático de trackers",
            variable=discovery_enabled_var,
        ).grid(row=21, column=1, sticky=tk.W, padx=(10, 0), pady=(2, 8))

        def save_settings():
            try:
                download_path = download_path_var.get().strip()
                torrent_path = torrent_path_var.get().strip()
                port = port_var.get().strip()
                tracker_ip = tracker_ip_var.get().strip()
                tracker_port = tracker_port_var.get().strip()
                download_limit = download_limit_var.get().strip()
                upload_limit = upload_limit_var.get().strip()
                max_connections = max_connections_var.get().strip()
                tracker_health_interval = tracker_health_var.get().strip()
                discovery_interval = discovery_interval_var.get().strip()
                discovery_enabled = discovery_enabled_var.get()

                if not download_path:
                    messagebox.showwarning(
                        "Advertencia", "Debe especificar una carpeta de descargas."
                    )
                    return
                if not torrent_path:
                    messagebox.showwarning(
                        "Advertencia", "Debe especificar la carpeta de torrents (.p2p)."
                    )
                    return
                if not tracker_ip:
                    messagebox.showwarning(
                        "Advertencia", "Debe especificar la IP del tracker."
                    )
                    return
                if not tracker_port:
                    messagebox.showwarning(
                        "Advertencia", "Debe especificar el puerto del tracker."
                    )
                    return
                try:
                    tracker_port_int = int(tracker_port)
                    if tracker_port_int < 1 or tracker_port_int > 65535:
                        messagebox.showwarning(
                            "Advertencia",
                            "El puerto del tracker debe estar entre 1 y 65535.",
                        )
                        return
                except ValueError:
                    messagebox.showwarning(
                        "Advertencia", "El puerto del tracker debe ser numérico."
                    )
                    return
                try:
                    port_num = int(port)
                    if port_num < 1024 or port_num > 65535:
                        messagebox.showwarning(
                            "Advertencia", "El puerto debe estar entre 1024 y 65535."
                        )
                        return
                except ValueError:
                    messagebox.showwarning(
                        "Advertencia", "El puerto debe ser un número válido."
                    )
                    return
                try:
                    dl_limit_int = int(download_limit)
                    ul_limit_int = int(upload_limit)
                    max_conn_int = int(max_connections)
                    tracker_health_int = int(tracker_health_interval)
                    discovery_int = int(discovery_interval)
                    if dl_limit_int < 0 or ul_limit_int < 0:
                        raise ValueError("Los límites no pueden ser negativos")
                    if max_conn_int <= 0:
                        raise ValueError("Máx. conexiones debe ser > 0")
                    if tracker_health_int <= 0 or discovery_int <= 0:
                        raise ValueError("Los intervalos deben ser > 0")
                except ValueError:
                    messagebox.showwarning(
                        "Advertencia",
                        "Límites/intervalos deben ser valores numéricos válidos.",
                    )
                    return

                os.makedirs(download_path, exist_ok=True)
                os.makedirs(torrent_path, exist_ok=True)
                tracker_address = f"{tracker_ip}:{tracker_port}"

                self.config_manager.set("General", "download_path", download_path)
                self.config_manager.set("General", "torrent_path", torrent_path)
                self.config_manager.set("General", "listen_port", port)
                self.config_manager.set("General", "tracker_address", tracker_address)
                self.config_manager.set("General", "max_download_rate", download_limit)
                self.config_manager.set("General", "max_upload_rate", upload_limit)
                self.config_manager.set("General", "max_connections", max_connections)
                self.config_manager.set(
                    "General", "tracker_health_interval", tracker_health_interval
                )
                self.config_manager.set(
                    "General", "tracker_discovery_interval", discovery_interval
                )
                self.config_manager.set(
                    "General",
                    "tracker_discovery_enabled",
                    "true" if discovery_enabled else "false",
                )

                # IMPORTANTE: Guardar cambios al archivo
                self.config_manager.save()

                # Aplicar en caliente en la GUI
                self._tracker_health_interval = tracker_health_int
                self._discovery_interval = discovery_int
                self._discovery_enabled = discovery_enabled

                self.torrent_client.setup_session()

                messagebox.showinfo("Éxito", "Configuración guardada correctamente.")
                settings_window.destroy()
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Error al guardar configuración: {str(e)}"
                )

        separator5 = ttk.Separator(main_frame, orient="horizontal")
        separator5.grid(row=22, column=0, columnspan=3, sticky="ew", pady=15)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=23, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(
            button_frame, text="Cancelar", command=settings_window.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Guardar", command=save_settings, width=15).pack(
            side=tk.LEFT, padx=5
        )

    def browse_folder(self, var, parent_window):
        initial_dir = var.get() if var.get() else "./"
        folder = filedialog.askdirectory(
            parent=parent_window,
            title="Seleccionar Carpeta de Descargas",
            initialdir=initial_dir,
            mustexist=False,
        )
        if folder:
            var.set(folder)
            messagebox.showinfo(
                "Carpeta Seleccionada",
                f"Carpeta de descargas configurada:\n{folder}",
                parent=parent_window,
            )

    def create_torrent(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo para compartir",
            filetypes=[("Todos los archivos", "*.*")],
        )

        if filename:
            try:
                address = self.config_manager.get_tracker_address()
                torrent_file, torrent_data = self.torrent_client.create_torrent_file(
                    filename, address
                )
                msg = "Torrent creado exitosamente:\n\n"
                msg += f"Archivo: {torrent_data.file_name}\n"
                msg += f"Tamaño: {torrent_data.display_size}\n"
                msg += f"Chunks: {torrent_data.total_chunks}\n"
                msg += f"Hash: {torrent_data.file_hash[:16]}...\n\n"
                msg += f"Archivo torrent guardado en:\n{torrent_file}"

                messagebox.showinfo("Torrent Creado", msg)

                # Agregar automáticamente a la lista de torrents (ya está en seeding)
                # El torrent ya fue agregado en create_torrent_file, solo actualizamos UI
                self.status_message.config(
                    text=f"Torrent creado y agregado: {torrent_data.file_name} (100%)"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Error al crear torrent: {str(e)}")

    def connect_to_peer(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Conectar a Peer")
        dialog.geometry("400x200")
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame, text="Dirección IP del Peer:", font=("TkDefaultFont", 10, "bold")
        ).pack(pady=(0, 10))

        ttk.Label(frame, text="Host/IP:").pack(anchor=tk.W)
        host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(frame, textvariable=host_var, width=30).pack(pady=5)

        ttk.Label(frame, text="Puerto:").pack(anchor=tk.W, pady=(10, 0))
        port_var = tk.StringVar(value=str(self.config_manager.get_listen_port()))
        ttk.Entry(frame, textvariable=port_var, width=30).pack(pady=5)

        def do_connect():
            try:
                host = host_var.get().strip()
                port = int(port_var.get().strip())

                if self.torrent_client.connect_to_peer(host, port):
                    messagebox.showinfo("Éxito", f"Conectado a peer {host}:{port}")
                    self.status_message.config(text=f"Conectado a {host}:{port}")
                    dialog.destroy()
                else:
                    messagebox.showerror(
                        "Error", f"No se pudo conectar a {host}:{port}"
                    )
            except ValueError:
                messagebox.showerror("Error", "Puerto inválido")
            except Exception as e:
                messagebox.showerror("Error", f"Error al conectar: {str(e)}")

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=(20, 0))

        ttk.Button(button_frame, text="Conectar", command=do_connect, width=15).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            button_frame, text="Cancelar", command=dialog.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)

    def show_about(self):
        messagebox.showinfo(
            "Acerca de",
            "Cliente P2P con Protocolo Personalizado\nVersión 2.0\n\nDesarrollado con Python y Tkinter\nProtocolo basado en sockets",
        )

    def pause_selected(self):
        selected = self.tree.selection()
        if not selected:
            self.status_message.config(
                text="Seleccione al menos un torrent para pausar"
            )
            return

        func = self.torrent_client.pause_torrent
        self._selected_action(selected, func, msg="Torrents pausados")

    def resume_selected(self):
        selected = self.tree.selection()
        if not selected:
            self.status_message.config(
                text="Seleccione al menos un torrent para reanudar"
            )
            return

        func = self.torrent_client.resume_torrent
        self._selected_action(selected, func, msg="Torrents reanudados")

    def remove_selected(self):
        selected = self.tree.selection()
        if not selected:
            self.status_message.config(
                text="Seleccione al menos un torrent para eliminar"
            )
            return

        if not messagebox.askyesno(
            "Confirmar", f"¿Desea eliminar {len(selected)} torrents seleccionados?"
        ):
            return

        def func(iid):
            self.torrent_client.remove_torrent(iid)
            if self.tree.exists(iid):
                self.tree.delete(iid)

        self._selected_action(
            selected, func, msg=f"Torrents eliminados: {len(selected)}"
        )

    def _selected_action(self, selected, action, msg=None):
        errors = []
        for iid in selected:
            try:
                action(iid)
            except Exception as e:
                logger.error(f"Error ejecutando acción en {iid}: {e}")
                errors.append(str(e))

        if errors:
            messagebox.showerror(
                "Errores",
                f"Se encontraron {len(errors)} errores:\n" + "\n".join(errors[:3]),
            )
        elif msg:
            self.status_message.config(text=msg)

    @staticmethod
    def _format_rate(kb_per_s: float) -> str:
        if kb_per_s >= 1024:
            return f"{kb_per_s / 1024:.2f} MB/s"
        return f"{kb_per_s:.1f} KB/s"

    @staticmethod
    def _format_eta(eta_seconds: Optional[float]) -> str:
        if eta_seconds is None:
            return "--"
        if eta_seconds <= 0:
            return "00:00"

        total_seconds = int(eta_seconds)
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _format_state(state: str) -> str:
        labels = {
            "queued": "En cola",
            "downloading": "Descargando",
            "stalled": "Sin peers",
            "paused": "Pausado",
            "seeding": "Compartiendo",
            "completed": "Completado",
            "error": "Error",
            "checking": "Verificando",
        }
        return labels.get(state, state)

    def update_torrents(self):
        try:
            handles = self.torrent_client.get_all_torrents()

            total_download = 0
            total_upload = 0
            total_peers = 0
            active_torrents = 0

            for iid in handles:
                try:
                    status = self.torrent_client.get_status(iid)

                    # Formatear tamaños usando humanize
                    file_size_str = humanize.naturalsize(status.file_size, binary=True)
                    downloaded_size_str = humanize.naturalsize(
                        status.downloaded_size, binary=True
                    )

                    logger.debug(f"[GUI_UPDATE] Torrent: {status.file_name}")
                    logger.debug(
                        f"[GUI_UPDATE] Status - size: {file_size_str}, downloaded: {downloaded_size_str}"
                    )
                    logger.debug(
                        f"[GUI_UPDATE] Status - progress: {status.progress:.1f}%, chunks: {status.total_chunks}"
                    )

                    total_download += status.download_rate
                    total_upload += status.upload_rate
                    total_peers += status.peers

                    if status.state in {"downloading", "stalled", "checking"}:
                        active_torrents += 1

                    values = (
                        status.file_name,
                        self._format_state(status.state),
                        file_size_str,
                        downloaded_size_str,
                        f"{status.progress:.1f}",
                        status.peers,
                        self._format_rate(status.download_rate),
                        self._format_rate(status.upload_rate),
                        self._format_eta(status.eta_seconds),
                        f"{status.total_chunks:.0f}",
                    )

                    wargs = {"values": values}
                    if self.tree.exists(iid):
                        self.tree.item(iid, **wargs)
                    else:
                        self.tree.insert("", tk.END, iid=iid, **wargs)
                except Exception as e:
                    logger.error(f"Error actualizando torrent {iid}: {e}")
                    # Continuar con los demás torrents
                    continue

            num_torrents = len(handles)
            self.torrents_label.config(
                text=f"Torrents: {num_torrents} ({active_torrents} activos)"
            )

            if total_download > 1024:
                self.download_speed_label.config(
                    text=f"Descarga: {total_download / 1024:.2f} MB/s"
                )
            else:
                self.download_speed_label.config(
                    text=f"Descarga: {total_download:.1f} KB/s"
                )

            if total_upload > 1024:
                self.upload_speed_label.config(
                    text=f"Subida: {total_upload / 1024:.2f} MB/s"
                )
            else:
                self.upload_speed_label.config(text=f"Subida: {total_upload:.1f} KB/s")

            self.peers_label.config(text=f"Peers: {total_peers}")

            tracker_connected = (
                self.torrent_client.tracker_manager.is_tracker_session_active()
            )

            # Actualizar tracker actual
            current_tracker = self.torrent_client.tracker_manager.get_current_tracker()
            if tracker_connected and current_tracker:
                host, port = current_tracker
                display_ip = self.torrent_client.tracker_manager.get_tracker_display_ip(
                    host
                )
                self.tracker_label.config(
                    text=f"Conectado a {display_ip}:{port}", foreground="green"
                )
            else:
                self.tracker_label.config(
                    text="Tracker conectado a --", foreground="gray"
                )

            self._refresh_tracker_status_table()

            # Health-check periódico de trackers
            if not self._tracker_health_running:
                now = datetime.now()
                if (
                    self._last_tracker_health is None
                    or (now - self._last_tracker_health).total_seconds()
                    >= self._tracker_health_interval
                ):
                    self._last_tracker_health = now
                    health_thread = threading.Thread(
                        target=self._refresh_tracker_health_background,
                        daemon=True,
                    )
                    health_thread.start()

            # Discovery periódico de trackers (cada 60 segundos)
            if self._discovery_enabled and not self._discovery_running:
                now = datetime.now()
                if (
                    self._last_discovery is None
                    or (now - self._last_discovery).total_seconds()
                    >= self._discovery_interval
                ):
                    self._last_discovery = now
                    # Ejecutar discovery en thread separado para no bloquear GUI
                    thread = threading.Thread(
                        target=self._discover_trackers_background, daemon=True
                    )
                    thread.start()

        except Exception as e:
            logger.error(f"Error crítico actualizando torrents: {e}", exc_info=True)
            # No mostrar error al usuario en cada update, solo loggear

        # Continuar el loop incluso si hubo errores
        self.root.after(1000, self.update_torrents)

    def _refresh_tracker_status_table(self):
        """Renderiza trackers y estado en la tabla de UI."""
        if not hasattr(self, "trackers_tree"):
            return

        for iid in self.trackers_tree.get_children():
            self.trackers_tree.delete(iid)

        statuses = self.torrent_client.tracker_manager.get_tracker_statuses()
        for status in statuses:
            tracker_name = (
                f"{status.get('display_ip', status['host'])}:{status['port']}"
            )

            state = status.get("state", "down")
            if state == "active":
                state_text = "Activo"
            elif state == "checking":
                state_text = "Comprobando"
            else:
                state_text = "Ausente"

            latency_ms = status.get("latency_ms")
            latency_text = (
                f"{latency_ms:.0f} ms" if isinstance(latency_ms, (int, float)) else "--"
            )

            last_check = status.get("last_check")
            if isinstance(last_check, (int, float)):
                last_check_text = datetime.fromtimestamp(last_check).strftime(
                    "%H:%M:%S"
                )
            else:
                last_check_text = "--"

            self.trackers_tree.insert(
                "",
                tk.END,
                values=(tracker_name, state_text, latency_text, last_check_text),
                tags=(state,),
            )

    def _refresh_tracker_health_background(self):
        """Hace health-check de trackers en un hilo para no bloquear GUI."""
        if self._tracker_health_running:
            return

        self._tracker_health_running = True
        try:

            async def refresh_health():
                await self.torrent_client.tracker_manager.refresh_tracker_health_async(
                    timeout=2.0
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(refresh_health())
            finally:
                loop.close()
        except Exception as e:
            logger.debug(f"Health-check de trackers falló: {e}")
        finally:
            self._tracker_health_running = False

    def _discover_trackers_background(self):
        """Descubre trackers en background (ejecuta en thread separado)"""
        if self._discovery_running:
            return

        self._discovery_running = True
        try:
            # Importar aquí para evitar errores si bit_lib no está disponible
            from bit_lib.services import DockerDNSDiscovery

            async def discover():
                discovered = set()
                client_ip = self._get_client_ip()
                _, tracker_port = self.config_manager.get_tracker_address()
                service_name = "tracker"

                try:
                    # DNS Discovery
                    dns = DockerDNSDiscovery(client_ip, tracker_port)
                    ips = await dns.resolve_service(service_name, use_cache=False)
                    for ip in ips:
                        discovered.add((ip, tracker_port))
                    logger.debug(f"DNS discovery: {len(ips)} trackers encontrados")
                except Exception as e:
                    logger.debug(f"DNS discovery falló: {e}")

                # Descubrimiento dirigido: trackers esperados por nombre
                for tracker_host in self._get_expected_tracker_hosts():
                    discovered.add((tracker_host, tracker_port))

                return discovered

            # Crear nuevo event loop para este thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                discovered = loop.run_until_complete(discover())

                # Añadir trackers descubiertos
                for host, port in discovered:
                    self.torrent_client.tracker_manager.add_tracker(host, port)

                if discovered:
                    logger.info(f"Discovery encontró {len(discovered)} trackers")
            finally:
                loop.close()

        except ImportError:
            logger.warning("bit_lib.services no disponible, discovery deshabilitado")
            self._discovery_enabled = False
        except Exception as e:
            logger.error(f"Error en discovery: {e}")
        finally:
            self._discovery_running = False

    @staticmethod
    def _get_client_ip() -> str:
        """Obtiene la IP del cliente"""
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            return "127.0.0.1"
