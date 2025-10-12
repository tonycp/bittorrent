from dotenv import load_dotenv

from .handlers.tracker import TrackerController
from .server.tracker import ThreadedServer, TrackerHandler
from .repos import DatabaseManager, DBM
from .schema import *
from .const import *


def start_server(middleware: DBM, settings: Dict[str, Any]) -> None:
    address = (
        settings.get("TRACKER_HOST", "0.0.0.0"),
        int(settings.get("TRACKER_PORT", 8000)),
    )

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
    settings = get_settings()

    db_manager = DatabaseManager(settings[DB_URL])
    db_manager.init_db(Entity.metadata)

    handlers = [TrackerController]  # Usa tu lista de controladores/handlers
    middleware = DBM(db_manager, handlers)

    start_server(middleware, settings)


if __name__ == "__main__":
    main()
