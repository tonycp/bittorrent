from bit_lib.const import c_status as cs
from bit_lib.models.typing import Data

from typing import Optional
from abc import ABC


class BaseError(Exception, ABC):
    def __init__(
        self,
        message: str,
        status: int,
        details: Optional[Data] = None,
    ):
        self.message = message
        self.status = status
        self.details = details
        super().__init__(message)

    def to_dict(self) -> Data:
        return {
            "message": self.message,
            "status": self.status,
            "details": self.details,
        }


class InvalidArgumentError(BaseError):
    def __init__(self, message: str):
        super().__init__(
            status=cs.INVALID_ARGUMENT_ERROR,
            message=message,
        )


class ServiceError(BaseError):
    def __init__(
        self,
        details: Optional[Data] = None,
    ):
        message = "Internal Error"
        super().__init__(
            status=cs.INTERNAL_ERROR,
            message=message,
            details=details,
        )
