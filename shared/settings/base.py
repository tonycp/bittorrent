from pydantic_settings import (
    BaseSettings as Settings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings_logging import (
    FormatterConfig,
    LoggingSettings,
    RootLoggerConfig,
    StreamHandlerConfig,
    TimedRotatingFileHandlerConfig,
)


class BaseSettings(Settings):
    logging: LoggingSettings = LoggingSettings(
        formatters={
            "detailed": FormatterConfig(
                format="%(asctime)s - %(name)s - %(levelname)s: %(message)s",
            ),
            "thread": FormatterConfig(
                format="%(asctime)s - (%(threadName)s:%(thread)d) - %(levelname)s => %(message)s",
            ),
        },
        handlers={
            "console": StreamHandlerConfig(
                level="INFO",
                formatter="detailed",
            ),
            "file": TimedRotatingFileHandlerConfig(
                filename="tracker",
                level="INFO",
                when="M",
                interval=15,
                formatter="detailed",
            ),
        },
        root=RootLoggerConfig(
            level="INFO",
            handlers=["console"],
        ),
    )

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
