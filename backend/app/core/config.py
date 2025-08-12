from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings


class RedisConfiguration(BaseSettings):
    url: RedisDsn = Field(..., alias="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class NERModelConfiguration(BaseSettings):
    model_name: str = Field(..., alias="NER_MODEL_NAME")
    model_version: str = Field(..., alias="NER_MODEL_VERSION")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
