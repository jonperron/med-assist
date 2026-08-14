from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    url: RedisDsn = Field(..., alias="REDIS_URL")
    retention_ttl_seconds: int = Field(
        default=3600,
        alias="RETENTION_TTL_SECONDS",
        gt=0,
        description="Lifetime of every stored value, in seconds.",
    )


class NERModelConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    model_name: str = Field(..., alias="NER_MODEL_NAME")
