from functools import lru_cache

from app.core.config import NERModelConfiguration, RedisConfiguration
from app.db.redis import RedisStorage
from app.services.file_handler import FileHandler


@lru_cache()
def get_redis_config() -> RedisConfiguration:
    return RedisConfiguration()


@lru_cache()
def get_redis_storage() -> RedisStorage:
    return RedisStorage(config=get_redis_config())


@lru_cache()
def get_file_handler() -> FileHandler:
    """Get file handler instance with Redis storage."""
    return FileHandler(redis_storage=get_redis_storage())


@lru_cache()
def get_ner_model_config() -> NERModelConfiguration:
    return NERModelConfiguration()
