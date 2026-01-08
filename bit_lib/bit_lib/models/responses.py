from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, Dict

from .message import Request


class SuccessResponse(BaseModel):
    status: str = Field(default="ok", description="Estado de la operación.")
    message: Optional[str] = Field(None, description="Mensaje de confirmación.")


class DataResponse(SuccessResponse):
    """Respuesta genérica con datos arbitrarios"""
    data: Dict[str, Any] = Field(description="Datos de la respuesta.")


class HandshakeSuccess(SuccessResponse):
    protocol_version: str


class DisconnectSuccess(SuccessResponse):
    pass


class KeepaliveSuccess(SuccessResponse):
    last_announce: datetime = Field(description="Nuevo timestamp de actividad.")


class RegisterSuccess(SuccessResponse):
    info_hash: str


class EventSuccess(SuccessResponse):
    request: Request
