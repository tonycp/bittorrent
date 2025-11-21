from typing import Any, Callable, Dict, Tuple, Type, TypeAlias, Union
from pydantic import BaseModel, TypeAdapter

Validated: TypeAlias = Union[TypeAdapter, Any]
ValidateType: TypeAlias = Union[TypeAdapter, BaseModel]

Data: TypeAlias = Dict[str, Any]
DataSet: TypeAlias = Dict[str, Type[ValidateType]]

Hook: TypeAlias = Callable[[ValidateType], str]
Handler: TypeAlias = Callable[[ValidateType], Any]
Controller: TypeAlias = Callable[..., Any]

HdlDec: TypeAlias = Callable[[Controller], Handler]
HdlInfo: TypeAlias = Tuple[Handler, DataSet]
