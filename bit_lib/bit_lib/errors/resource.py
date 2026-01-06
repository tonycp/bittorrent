from bit_lib.const import c_status as cs
from .errors import BaseError


class ResourceError(BaseError):
    def __init__(self, message: str, status: int, **kwargs):
        message = message.format(**kwargs)
        details = kwargs.copy()
        super().__init__(message, status, details)


class NotFoundError(ResourceError):
    def __init__(self, res_id: str, res_type: str):
        message = "{res_type} with info hash {res_id} not found"
        super().__init__(
            status=cs.NOT_FOUND_ERROR,
            message=message,
            res_id=res_id,
            res_type=res_type,
        )


class ResourceConflictError(ResourceError):
    def __init__(self, res_id: str, res_type: str):
        message = "{res_type} with info hash {res_id} already exists"
        super().__init__(
            status=cs.INVALID_ARGUMENT_ERROR,
            message=message,
            res_id=res_id,
            res_type=res_type,
        )


class NotAssociatedError(ResourceError):
    def __init__(
        self,
        from_id: str,
        to_id: str,
        from_type: str,
        to_type: str,
    ):
        message = "{from_type} {from_id} is not associated with {to_type} {to_id}"
        super().__init__(
            status=cs.NOT_FOUND_ERROR,
            message=message,
            from_id=from_id,
            to_id=to_id,
            from_type=from_type,
            to_type=to_type,
        )
