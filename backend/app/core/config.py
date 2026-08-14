from typing import Optional

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
    encryption_key: Optional[str] = Field(
        default=None,
        alias="STORAGE_ENCRYPTION_KEY",
        description=(
            "Fernet key used to encrypt every stored value. When unset, an "
            "ephemeral key is generated at startup, so a dump taken from a "
            "stopped process is inert."
        ),
    )


class PrivacyConfiguration(BaseSettings):
    """Knobs that decide how much of a document survives the request."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    store_document_text: bool = Field(
        default=False,
        alias="STORE_DOCUMENT_TEXT",
        description=(
            "Keep the extracted document text alongside the entities. Off by "
            "default: only the categorised entities are persisted."
        ),
    )
    pseudonymize: bool = Field(
        default=True,
        alias="PSEUDONYMIZE_ENTITIES",
        description=(
            "Mask detected patient identifiers before they are returned or "
            "stored. On by default; a request may ask for masking but cannot "
            "turn it off. Setting this to false is a deliberate decision to "
            "handle identifiable patient data."
        ),
    )


class NERModelConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    model_name: str = Field(..., alias="NER_MODEL_NAME")
