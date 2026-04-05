from pydantic import BaseModel, TypeAdapter, ValidationError

from typing import (
    Callable,
    Dict,
    Set,
    Any,
)
from bit_lib.models import (
    Data,
    DataSet,
    Validated,
)

ERROR_MESSAGE = "{func} {msg}: {name}"


def _get_names_error(func, message: str, error: str, missings: Set[str]):
    length = len(missings)
    s = "" if length == 1 else "s"
    error = error.format(length=length, s=s)
    last = missings.pop()

    args = [", ".join(missings), last]
    name = " and ".join(args if args[0] else args[1:])
    msg = message.format(func=func.__name__, msg=error, name=name)
    return TypeError(msg)


def _names_validate(
    func: Callable,
    names: set[str],
    keys: Set[str],
):
    missings = names.difference(keys)
    extra = keys.difference(names)

    if missings:
        error = "missing {length} required positional argument{s}"
        raise _get_names_error(func, ERROR_MESSAGE, error, missings)

    if extra:
        error = "got {length} unexpected keyword argument{s}"
        raise _get_names_error(func, ERROR_MESSAGE, error, extra)


def _models_validate(func_name, data: Data, dataset: DataSet) -> Dict[str, Validated]:
    _names_validate(func_name, set(data.keys()), set(dataset.keys()))

    def _validate(item):
        key, value = item
        try:
            if dataset[key] is Any:
                return key, value
            if dataset[key] is BaseModel:
                return key, dataset[key].model_validate(value)
            if value is None:
                return key, value
            adapter = TypeAdapter(dataset[key])
            return key, adapter.validate_python(value)
        except ValidationError as e:
            raise ValueError(f"Error validating {key} for handler {func_name}: {e}")

    return dict(map(_validate, data.items()))
