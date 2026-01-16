from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm.properties import MappedColumn
from typing import Optional, TypeAlias
from datetime import datetime
from uuid import UUID


EntityID: TypeAlias = UUID


class Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[EntityID] = None
    version: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def set_datetime_defaults(cls, v):
        return None if isinstance(v, MappedColumn) and v.column.default else v
