import traceback, debugpy
import tkinter as tk

from dotenv import load_dotenv

from src.const import DEBUG
from src.config import *
from src.gui import BitTorrentClientGUI


def main():
    load_dotenv()

    settings = get_env_settings()

    if settings[DEBUG]:
        debugpy.listen(("0.0.0.0", 5678))
        print("Esperando debugger VS Code...")
        debugpy.wait_for_client()

    try:
        root = tk.Tk()
        BitTorrentClientGUI(root)
        root.mainloop()
    except Exception as e:
        print("ERROR FATAL:", e)
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
