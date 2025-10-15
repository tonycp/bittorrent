import tkinter as tk

from tkinter import ttk, filedialog, messagebox
from typing import List

from widgets import *
from styles.container import container_


from .config_manager import ConfigManager


class BitTorrentClient(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("BitTorrent Client")
        self.geometry("800x500")

        # Contenedor principal: apila todos los frames
        container = tk.Frame(self)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        container.configure(container_)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Inicializa frames (vistas/paneles)
        self.frames = {}
        self.init_frames(container)

    def init_frames(self, container):
        self.frames = dict([(F, F(container, self)) for F in widgets])
        self.frames[NavBar].grid_configure(
            column=0,
        )

    def show_frame(self, page_class):
        frame = self.frames[page_class]
        frame.tkraise()
