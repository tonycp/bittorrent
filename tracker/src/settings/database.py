from pydantic import BaseModel


class DBSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///tracker.db"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
