from dotenv import load_dotenv

from const import *
from torrent_client.client import BitTorrentClient

# Load environment variables from env file
load_dotenv()


def main():
    settings = get_settings()
    app = BitTorrentClient()
    app.mainloop()


if __name__ == "__main__":
    main()
