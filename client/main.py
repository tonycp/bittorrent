from dotenv import load_dotenv
import os
from torrent_client.client import BitTorrentClient

# Load environment variables from .env file
load_dotenv()

def main():
    db_url = os.getenv("DATABASE_URL", "sqlite:///client.db")
    print(f"Client connected to database at {db_url}")
    app = BitTorrentClient()
    app.mainloop()

if __name__ == "__main__":
    main()
