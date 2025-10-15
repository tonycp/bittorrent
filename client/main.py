from dotenv import load_dotenv

from src.const import *
from src.views.client import BitTorrentClient


def main():
    load_dotenv()
    settings = get_settings()

    app = BitTorrentClient()
    app.mainloop()


if __name__ == "__main__":
    main()
