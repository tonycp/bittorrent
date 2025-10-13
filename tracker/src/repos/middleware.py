from typing import Any, Callable, Dict, List, Type
from contextlib import contextmanager
from sqlalchemy.orm import Session

from .manager import DatabaseManager

__all__ = ["DBM"]


class DBM:
    def __init__(
        self,
        db_manager: DatabaseManager,
        handlers: List[Type[Any]],
    ):
        self.db_manager = db_manager
        self.SessionLocal = db_manager.SessionLocal
        self.handlers = handlers

    @contextmanager
    def session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def register_handler(self, session: Session) -> Dict[str, Any]:
        handlers: Dict[str, Any] = {}
        for h in self.handlers:
            handlers[h.__name__] = h(session)
        return handlers

    def __call__(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs):
            with self.session_scope() as session:
                handlers = self.register_handler(session)
                return handler(*args, handlers=handlers, **kwargs)

        return wrapper
