from typing import Any, Callable, Dict, Tuple, TypeAlias

Data: TypeAlias = Dict[str, Any]
DataSet: TypeAlias = Dict[str, TypeAlias]

Hook: TypeAlias = Callable[[Dict[str, Any]], str]
Handler: TypeAlias = Callable[[Dict[str, Any]], Any]
Controller: TypeAlias = Callable[..., Any]

HdlDecorator: TypeAlias = Callable[[Controller], Handler]
HdlInfo: TypeAlias = Tuple[Handler, DataSet]
