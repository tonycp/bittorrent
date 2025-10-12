import tkinter as tk

from tkinter import messagebox
from tkinter import ttk
from typing import List

from .widgets import *
from .styles.container import container_


class BitTorrentClient(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("BitTorrent Client")
        container = tk.Frame(self)
        container.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True,
        )
        container.configure(container_)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.init_frames(container)

    def init_frames(self, container):
        self.frames = dict([(F, F(container, self)) for F in widgets])
        self.frames[NavBar].grid_configure(
            column=0,
        )
