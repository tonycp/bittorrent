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
        self.column("name", width=200)
        self.column("progress", width=80, anchor="center")
        self.column("status", width=100, anchor="center")
        # ... sigue con las demás columnas

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
