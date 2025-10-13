import tkinter as tk

from .styles.container import container_


class NavBar(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.configure(container_)
        self.controller = controller
