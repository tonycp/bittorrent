import socket
from dotenv import load_dotenv

from src.handlers.tracker import TrackerController
from src.server.tracker import ThreadedServer, TrackerHandler
from src.repos import DatabaseManager, DBM
from src.schema import *
from src.const import *


def start_server(middleware: DBM, settings: Dict[str, Any]) -> None:
    address = (settings[TRK_HOST], int(settings[TRK_PORT]))

    server = ThreadedServer(address, TrackerHandler, middleware=middleware)
    print(f"BitTorrent tracker activo en {address}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Tracker detenido manualmente.")
    finally:
        server.shutdown()


def main():
    load_dotenv()
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    settings = get_settings({TRK_HOST: ip})

    db_manager = DatabaseManager(settings[DB_URL])
    db_manager.init_db(Entity.metadata)

    handlers = [TrackerController]  # Usa tu lista de controladores/handlers
    middleware = DBM(db_manager, handlers)

    start_server(middleware, settings)


if __name__ == "__main__":
    main()
