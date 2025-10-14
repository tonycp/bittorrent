from dotenv import load_dotenv

from const import *
from torrent_client.client import BitTorrentClient


def main():
    load_dotenv()
    settings = get_settings()

    app = BitTorrentClient()
    app.mainloop()


if __name__ == "__main__":
    main()
