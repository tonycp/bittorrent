from __future__ import annotations

from typing import Any, Callable, Awaitable, Dict, Self, Tuple, Type, TypeAlias, Union, TYPE_CHECKING
from pydantic import BaseModel, TypeAdapter

if TYPE_CHECKING:
	from .responses import SuccessResponse
else:
	SuccessResponse = object

Validated: TypeAlias = Union[TypeAdapter, Any]
ValidateType: TypeAlias = Union[TypeAdapter, BaseModel]

Data: TypeAlias = Dict[str, Any]
DataSet: TypeAlias = Dict[str, Type[ValidateType]]

Hook: TypeAlias = Callable[[ValidateType], str]
Handler: TypeAlias = Callable[[Self, ValidateType], Awaitable[SuccessResponse]]
Controller: TypeAlias = Callable[..., Any]

HdlDec: TypeAlias = Callable[[Controller], Handler]
HdlInfo: TypeAlias = Tuple[Handler, DataSet]
