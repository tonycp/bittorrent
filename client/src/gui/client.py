import os, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ..config.config_mng import ConfigManager
from ..core.torrent_client import TorrentClient


class BitTorrentClientGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cliente BitTorrent")
        self.root.geometry("900x600")

        self.config_manager = ConfigManager()
        self.torrent_client = TorrentClient(self.config_manager)

        self.setup_menu()
        self.setup_ui()

        self.update_torrents()

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

        columns = ("Nombre", "Tamaño", "Descargado", "Progreso", "Chunks")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        self.tree.heading("Nombre", text="Archivo")
        self.tree.heading("Tamaño", text="Tamaño (bytes)")
        self.tree.heading("Descargado", text="Descargado")
        self.tree.heading("Progreso", text="Progreso (%)")
        self.tree.heading("Chunks", text="Chunks")

        self.tree.column("Nombre", width=300)
        self.tree.column("Tamaño", width=100, anchor=tk.E)
        self.tree.column("Descargado", width=100, anchor=tk.E)
        self.tree.column("Progreso", width=100, anchor=tk.E)
        self.tree.column("Chunks", width=100, anchor=tk.E)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.grid(row=2, column=0, sticky="ew", pady=(10, 5))

        status_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=3, column=0, sticky="ew", pady=(5, 0))

        left_status_frame = ttk.Frame(status_frame)
        left_status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=3)

        self.connection_label = ttk.Label(
            left_status_frame, text="🔌 Desconectado", foreground="red"
        )
        self.connection_label.pack(side=tk.LEFT, padx=(0, 15))

        self.torrents_label = ttk.Label(left_status_frame, text="📦 Torrents: 0")
        self.torrents_label.pack(side=tk.LEFT, padx=(0, 15))

        self.download_speed_label = ttk.Label(
            left_status_frame, text="⬇️ Descarga: 0.0 KB/s"
        )
        self.download_speed_label.pack(side=tk.LEFT, padx=(0, 15))

        self.upload_speed_label = ttk.Label(
            left_status_frame, text="⬆️ Subida: 0.0 KB/s"
        )
        self.upload_speed_label.pack(side=tk.LEFT, padx=(0, 15))

        self.peers_label = ttk.Label(left_status_frame, text="👥 Peers: 0")
        self.peers_label.pack(side=tk.LEFT)

        right_status_frame = ttk.Frame(status_frame)
        right_status_frame.pack(side=tk.RIGHT, padx=5, pady=3)

        self.status_message = ttk.Label(
            right_status_frame, text="Listo", foreground="gray"
        )
        self.status_message.pack(side=tk.RIGHT)

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

                msg = f"Nombre: {info['name']}\n"
                msg += f"Tamaño: {info['display_size']}\n"
                msg += f"Archivos: {info['num_files']}\n\n"
                msg += "¿Desea agregar este torrent?"

                if messagebox.askyesno("Información del Torrent", msg):
                    self.torrent_client.add_torrent(filename)
                    self.status_message.config(text=f"Torrent agregado: {info['name']}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al cargar torrent: {str(e)}")

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configuración del Cliente")
        settings_window.geometry("650x550")
        settings_window.resizable(False, False)

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
            text="📁 Buscar",
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
            text="📁 Buscar",
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

        def save_settings():
            try:
                download_path = download_path_var.get().strip()
                torrent_path = torrent_path_var.get().strip()
                port = port_var.get().strip()
                tracker_ip = tracker_ip_var.get().strip()
                tracker_port = tracker_port_var.get().strip()
                download_limit = download_limit_var.get().strip()
                upload_limit = upload_limit_var.get().strip()

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
                    int(download_limit)
                    int(upload_limit)
                except ValueError:
                    messagebox.showwarning(
                        "Advertencia",
                        "Los límites de velocidad deben ser números válidos.",
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

                self.torrent_client.setup_session()

                messagebox.showinfo("Éxito", "Configuración guardada correctamente.")
                settings_window.destroy()
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Error al guardar configuración: {str(e)}"
                )

        separator4 = ttk.Separator(main_frame, orient="horizontal")
        separator4.grid(row=16, column=0, columnspan=3, sticky="ew", pady=15)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=17, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(
            button_frame, text="❌ Cancelar", command=settings_window.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame, text="💾 Guardar", command=save_settings, width=15
        ).pack(side=tk.LEFT, padx=5)

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
                msg = f"Torrent creado exitosamente:\n\n"
                msg += f"Archivo: {torrent_data.file_name}\n"
                msg += f"Tamaño: {torrent_data.display_size}\n"
                msg += f"Chunks: {torrent_data.total_chunks}\n"
                msg += f"Hash: {torrent_data.file_hash[:16]}...\n\n"
                msg += f"Archivo torrent guardado en:\n{torrent_file}"

                messagebox.showinfo("Torrent Creado", msg)
                self.status_message.config(
                    text=f"Torrent creado: {torrent_data.file_name}"
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

        ttk.Button(button_frame, text="🔗 Conectar", command=do_connect, width=15).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            button_frame, text="❌ Cancelar", command=dialog.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)

    def show_about(self):
        messagebox.showinfo(
            "Acerca de",
            "Cliente P2P con Protocolo Personalizado\nVersión 2.0\n\nDesarrollado con Python y Tkinter\nProtocolo basado en sockets",
        )

    def pause_selected(self):
        selected = self.tree.selection()
        if not selected:
            return

        func = self.torrent_client.pause_torrent
        self._selected_action(selected, func, msg="Torrents pausados")

    def resume_selected(self):
        selected = self.tree.selection()
        if not selected:
            return

        func = self.torrent_client.resume_torrent
        self._selected_action(selected, func, msg="Torrents reanudados")

    def remove_selected(self):
        selected = self.tree.selection()
        if not selected:
            return

        if not messagebox.askyesno(
            "Confirmar", f"¿Desea eliminar {len(selected)} torrents seleccionados?"
        ):
            return

        func = lambda x: {
            self.torrent_client.remove_torrent(x),
            self.tree.delete(x),
        }
        self._selected_action(
            selected, func, msg=f"Torrents eliminados: {len(selected)}"
        )

    def _selected_action(self, selected, action, msg=None):
        for iid in selected:
            action(iid)

        if msg:
            self.status_message.config(text=msg)

    def update_torrents(self):
        try:
            handles = self.torrent_client.get_all_torrents()

            total_download = 0
            total_upload = 0
            total_peers = 0
            active_torrents = 0

            for iid in handles:
                status = self.torrent_client.get_status(iid)
                values = (
                    status.file_name,
                    f"{status.file_size:.1f}",
                    f"{status.downloaded_size:.1f}",
                    f"{status.progress:.1f}",
                    f"{status.total_chunks:.1f}",
                )

                wargs = {"values": values}
                if self.tree.exists(iid):
                    self.tree.item(iid, **wargs)
                else:
                    self.tree.insert("", tk.END, iid=iid, **wargs)

            num_torrents = len(handles)
            self.torrents_label.config(
                text=f"📦 Torrents: {num_torrents} ({active_torrents} activos)"
            )

            if total_download > 1024:
                self.download_speed_label.config(
                    text=f"⬇️ Descarga: {total_download/1024:.2f} MB/s"
                )
            else:
                self.download_speed_label.config(
                    text=f"⬇️ Descarga: {total_download:.1f} KB/s"
                )

            if total_upload > 1024:
                self.upload_speed_label.config(
                    text=f"⬆️ Subida: {total_upload/1024:.2f} MB/s"
                )
            else:
                self.upload_speed_label.config(
                    text=f"⬆️ Subida: {total_upload:.1f} KB/s"
                )

            self.peers_label.config(text=f"👥 Peers: {total_peers}")

            if num_torrents > 0 or total_peers > 0:
                self.connection_label.config(text="🔌 Conectado", foreground="green")
            else:
                self.connection_label.config(text="🔌 Desconectado", foreground="red")

        except Exception as e:
            print(f"Error actualizando torrents: {e}")

        self.root.after(1000, self.update_torrents)
