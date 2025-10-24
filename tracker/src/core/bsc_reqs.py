from typing import Callable, Any, Dict, List, Tuple, Optional, Type
from .bsc_hds import _handlers, _controllers

import json, logging


def extract_header(
    request: Dict[str, Any],
) -> Tuple[
    Tuple[
        Optional[str],
        Optional[str],
        Optional[str],
        List[str],
    ],
    Dict[str, Any],
]:
    """Extract the header from the incoming data."""
    try:
        data: Dict[str, Any] = request.get("args", {})
        controller_name: Optional[str] = request.get("controller")
        command_name: Optional[str] = request.get("command")
        func_name: Optional[str] = request.get("func")
        args: List[str] = list(data.keys())
        return (controller_name, command_name, func_name, args), data
    except Exception as e:
        logging.error(f"Error extracting header: {e}")
        raise ValueError("Invalid request format") from e


def load_data(
    data: Dict[str, Any], dataset: Dict[str, Callable[[Any], Any]]
) -> Dict[str, Any]:
    """Load and validate the data from the message into a dictionary."""

    result: Dict[str, Any] = {}
    validated_errors: List[ValueError] = []
    for key, value_type in dataset.items():
        value = data.get(key)
        is_optional = getattr(value_type, "_name", None) == "Optional"
        if value is None and not is_optional:
            raise ValueError(f"Missing required key: {key}")
        elif is_optional:
            result[key] = None
            continue
        try:
            if isinstance(value, dict):
                result[key] = value_type(**value)
            else:
                result[key] = value_type(value)
        except Exception as e:
            validated_errors.append(ValueError(f"Error processing key '{key}': {e}"))

    if validated_errors:
        raise ValueError(f"Invalid data: {validated_errors}")

    return result


def handle_request(
    header: Tuple[Optional[str], str, str, List[str]],
    data: Dict[str, Any],
    handlers: Dict[str, Any],
) -> str:
    """Handle incoming requests and route them to the appropriate handler."""
    try:
        endpoint_name, command_name, func_name, data_header = header
        if command_name is None or func_name is None:
            raise ValueError("Missing command_name or func_name in header")

        endpoint_name = endpoint_name or ""
        args = ":?".join(data_header) + ":?"
        handler_key = f"{endpoint_name}//{command_name}//{func_name}//{args}"
        handler = _handlers.get(handler_key)

        if not handler:
            raise ValueError("Unknown command name or dataset")

        handler_func, dataset, is_class = handler
        logging.info(f"Handling request: {handler_key}")

        instance = handlers[_controllers[endpoint_name]] if is_class else None
        return handler_func(load_data(data, dataset), instance)
    except Exception as e:
        logging.error(f"Error handling request: {e}")
        return {"error": str(e)}
