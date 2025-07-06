from functools import lru_cache

from app.core.config import RedisConfiguration
from app.db.redis import RedisStorage


@lru_cache()
def get_redis_config() -> RedisConfiguration:
    return RedisConfiguration()

@lru_cache()
def get_redis_storage() -> RedisStorage:
    return RedisStorage(config=get_redis_config())