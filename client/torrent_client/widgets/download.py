import tkinter as tk
from tkinter import ttk
from ..styles.container import container_


class DownloadPanel(ttk.Treeview):
    def __init__(self, parent, controller):
        super().__init__(
            parent,
            columns=("name", "progress", "status", "speed", "seeds", "peers", "size"),
            show="headings",
        )
        self.controller = controller
        self.configure(container_)

        # Definir encabezados
        self.heading("name", text="Nombre")
        self.heading("progress", text="Progreso")
        self.heading("status", text="Estado")
        self.heading("speed", text="Velocidad")
        self.heading("seeds", text="Semillas")
        self.heading("peers", text="Pares")
        self.heading("size", text="Tamaño")

        # Opcional: definir anchura de columnas
        self.column("name", width=180, minwidth=100, anchor="w", stretch=True)
        self.column("progress", width=70, minwidth=50, anchor="center", stretch=True)
        self.column("status", width=90, minwidth=60, anchor="center", stretch=True)
        self.column("speed", width=80, minwidth=60, anchor="center", stretch=True)
        self.column("seeds", width=60, minwidth=40, anchor="center", stretch=True)
        self.column("peers", width=60, minwidth=40, anchor="center", stretch=True)
        self.column("size", width=90, minwidth=60, anchor="e", stretch=True)

        self.pack(fill=tk.BOTH, expand=True)

    def add_download(self, info):
        self.insert(
            "",
            "end",
            values=(
                info["name"],
                info["progress"],
                info["status"],
                info["speed"],
                info["seeds"],
                info["peers"],
                info["size"],
            ),
        )

    def update_download(self, info_hash, new_info):
        for item in self.get_children():
            if self.item(item, "values")[0] == info_hash:
                self.item(
                    item,
                    values=(
                        new_info["name"],
                        new_info["progress"],
                        new_info["status"],
                        new_info["speed"],
                        new_info["seeds"],
                        new_info["peers"],
                        new_info["size"],
                    ),
                )
                break

    def parse_tracker_to_panel(tracker_data, total_size):
        progress = int(100 * (total_size - tracker_data["left"]) / total_size)

        # Determina el estado
        if tracker_data.get("event") == "completed" or tracker_data["left"] == 0:
            status = "Completado"
        elif tracker_data.get("event") == "stopped":
            status = "Detenido"
        else:
            status = "Descargando"

        return {
            "name": tracker_data["info_hash"],
            "progress": f"{progress}%",
            "status": status,
            "speed": "?",  # Debes calcularlo si tienes la info (bytes/seg)
            "seeds": "?",  # Ideal: contar peers completos
            "peers": "?",  # Ideal: contar todos los peers conectados
            "size": f"{total_size/1024/1024:.2f} MB",
        }
