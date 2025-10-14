import tkinter as tk

from ..styles.container import container_


class NavBar(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.configure(container_)
        self.controller = controller

        btn_descargas = tk.Button(
            self,
            text="Descargas",
            command=lambda: controller.show_frame("DownloadPanel"),
        )
        btn_config = tk.Button(
            self,
            text="Configuración",
            command=lambda: controller.show_frame("ConfigPanel"),
        )
        btn_ayuda = tk.Button(
            self, text="Ayuda", command=lambda: controller.show_frame("HelpPanel")
        )

        btn_descargas.pack(side=tk.LEFT, padx=5, pady=5)
        btn_config.pack(side=tk.LEFT, padx=5, pady=5)
        btn_ayuda.pack(side=tk.LEFT, padx=5, pady=5)
