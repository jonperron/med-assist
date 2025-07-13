from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings


class RedisConfiguration(BaseSettings):
    url: RedisDsn = Field(..., env="REDIS_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
