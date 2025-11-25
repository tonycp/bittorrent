from pydantic_settings import (
    BaseSettings as Settings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from shared.settings.base import BaseSettings

from .services import ServiceSettings
from .database import DBSettings


class Configuration(Settings):
    database: DBSettings = DBSettings()
    services: ServiceSettings = ServiceSettings()
    base: BaseSettings = BaseSettings()

    model_config = SettingsConfigDict(
        json_file="config.json",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[Settings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (JsonConfigSettingsSource(settings_cls),)
