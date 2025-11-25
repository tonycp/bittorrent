from pydantic import BaseModel


class SocketSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5555


class ServiceSettings(BaseModel):
    tracker: SocketSettings = SocketSettings()
