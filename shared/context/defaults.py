from typing import Any, Callable, Dict
from functools import lru_cache

import configparser


def _only_default(_, y):
    return y


@lru_cache
def _get_constants(module):
    return {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper() and not name.startswith("__")
    }


def get_default_settings(
    settings: Dict[str, Dict[str, Any]],
    module_key,
    module_const,
    func: Callable[[str], str] = _only_default,
):
    getenv_map = {}
    env_key = _get_constants(module_key)
    env_default = _get_constants(module_const)

    for key, path in env_key.items():
        segments = path.split("_")
        section_key = segments[1] if len(segments) > 1 else "general"
        name = segments[0]

        default = env_default.get(f"DEFAULT_{key}")
        trans = func(path, default)

        section_def = settings.get(section_key, {})
        section = getenv_map.get(section_key, {})
        getenv_map[section_key] = section

        value = section_def.get(key, trans)
        section[name] = value

    return getenv_map


def save_config_to_ini(config: Dict[str, Any], filename="config.ini"):
    config_parser = configparser.ConfigParser()

    for section, settings in config.items():
        config_parser[section] = {k: str(v) for k, v in settings.items()}

    with open(filename, "w") as f:
        config_parser.write(f)
