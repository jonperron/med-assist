from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    url: RedisDsn = Field(..., alias="REDIS_URL")


class NERModelConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    model_name: str = Field(..., alias="NER_MODEL_NAME")
