from typing import Any, Dict, List

from shared.interface.typing import Data, DataSet


def _instance_data(value, v_type):
    if isinstance(value, dict):
        return v_type(**value)
    else:
        return v_type(value)


def load_data(data: Data, dataset: DataSet) -> Data:
    """Load and validate the data from the message into a dictionary."""

    result: Dict[str, Any] = {}
    errors: List[ValueError] = []
    for key, v_type in dataset.items():
        is_optional = getattr(v_type, "_name", None) == "Optional"
        value = data.get(key)
        result[key] = None

        if value:
            try:
                result[key] = _instance_data(value, v_type)
            except Exception as e:
                errors.append(ValueError(f"Error processing key '{key}': {e}"))
        elif not is_optional:
            errors.append(ValueError(f"Missing required key: {key}"))

    if errors:
        raise ValueError(f"Invalid data: {errors}")

    return result
