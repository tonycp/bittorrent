from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData


__all__ = ["DatabaseManager"]


class DatabaseManager:
    def __init__(self, url: str):
        self.engine: Engine = create_engine(url)
        self.SessionLocal: sessionmaker[Session] = sessionmaker(bind=self.engine)

    def init_db(self, metadata: MetaData) -> None:
        metadata.create_all(self.engine)

    def get_local_session(self) -> Session:
        return self.SessionLocal()
