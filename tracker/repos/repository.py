from typing import Type, TypeVar, Generic, Optional, List
from sqlalchemy.orm import Session

T = TypeVar("T")

__all__ = ["GenericRepository"]


class GenericRepository(Generic[T]):
    def __init__(self, session: Session, model_class: Type[T]):
        self.session: Session = session
        self.model_class: Type[T] = model_class

    def set_session(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, id_: str) -> Optional[T]:
        return self.session.query(self.model_class).filter_by(id=id_).first()

    def get_by_field(self, **kwargs) -> Optional[T]:
        return self.session.query(self.model_class).filter_by(**kwargs).first()

    def get_all(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[T]:
        query = self.session.query(self.model_class)
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def add(self, instance: T) -> None:
        self.session.add(instance)
