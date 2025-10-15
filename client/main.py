from dotenv import load_dotenv
import tkinter as tk

from .src.const import *
from .src.views import BitTorrentClientGUI


def main():
    load_dotenv()
    settings = get_settings({})

    root = tk.Tk()
    app = BitTorrentClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
