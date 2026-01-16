from bit_lib.tools import Descriptor, BaseController, ControllerMeta
from pydantic import BaseModel

from typing import Dict, Type
from bit_lib.errors import (
    InvalidArgumentError,
    ServiceError,
    BaseError,
)
from bit_lib.models import (
    Error,
    Response,
    Controller,
    Data,
    DataSet,
    Handler,
    HdlDec,
    HdlInfo,
)

from pydantic import ValidationError

from ._process import _models_validate, _names_validate

import logging

logger = logging.getLogger(__name__)


def create_decorator(command: str, dataset: DataSet) -> HdlDec:
    def decorator(func: Controller) -> Handler:
        return HandleDescriptor(command, func, dataset)

    return decorator


class HandleDescriptor(Descriptor):
    def __init__(self, command: str, func: Controller, dataset: DataSet):
        count = func.__code__.co_argcount
        args = func.__code__.co_varnames[1:count]
        keys = set(dataset.keys())
        names = set(args)

        _names_validate(func, names, keys)

        id = "".join(f"{arg}:?" for arg in args)
        super().__init__(command, func, id)

        self.dataset = dataset

    def register(self, owner: Type["BaseHandler"], index: str, wrapper: Handler):
        owner._handlers[index] = (wrapper, self.dataset)


class HandlerMeta(ControllerMeta):
    _handlers: Dict[str, HdlInfo] = None

    def __new__(cls, name, bases, namespace):
        return super().__new__(cls, name, bases, namespace)

    def __init__(cls, name, bases, namespace):
        cls._handlers = cls._handlers or {}
        super().__init__(name, bases, namespace)


class BaseHandler(BaseController, metaclass=HandlerMeta):
    @classmethod
    def get_handler(cls, sub_key: str) -> HdlInfo:
        result = cls._handlers.get(sub_key)
        if result is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Handler not found for key: '{sub_key}'. Available keys: {list(cls._handlers.keys())}")
            raise KeyError(f"Handler not found for key: {sub_key}")
        return result

    async def _exec_handler(self, hdl_key, data):
        handler, dataset = self.get_handler(hdl_key)
        validate_data = _models_validate(handler.__name__, data, dataset)
        response_data = await handler(self, validate_data)
        return response_data

    async def process(self, hdl_key: str, data: Data, reply_to: str = None) -> Response:
        try:
            response_data = await self._exec_handler(hdl_key, data)
            if isinstance(response_data, BaseModel):
                response_data = response_data.model_dump()
            return Response(data=response_data, reply_to=reply_to)
        except ValidationError as e:
            error_msg = f"Error de validación de entrada: {e.errors()}"
            logger.error(f"Handled validation error in handler {hdl_key}: {error_msg}")
            data_error = InvalidArgumentError(error_msg).to_dict()
        except BaseError as e:
            logger.error(f"Handled error in handler {hdl_key}: {e}")
            data_error = e.to_dict()
        except Exception as e:
            logger.error(f"Unhandled error in handler {hdl_key}: {e}")
            details = {"error_type": type(e).__name__}
            data_error = ServiceError(details=details).to_dict()

        return Error(data=data_error, reply_to=reply_to)
