from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings


class RedisConfiguration(BaseSettings):
    url: RedisDsn = Field(..., alias="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
