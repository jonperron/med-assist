from functools import lru_cache

from app.core.config import NERModelConfiguration, RedisConfiguration
from app.db.redis import RedisStorage
from app.repositories.text_repository import (
    RedisTextRepository,
    TextRepositoryInterface,
)


@lru_cache()
def get_redis_config() -> RedisConfiguration:
    return RedisConfiguration()


@lru_cache()
def get_redis_storage() -> RedisStorage:
    return RedisStorage(config=get_redis_config())


@lru_cache()
def get_text_repository() -> TextRepositoryInterface:
    """Get text repository instance."""
    return RedisTextRepository(redis_storage=get_redis_storage())


@lru_cache()
def get_entity_extractor():
    """Get entity extractor instance."""
    # Import here to avoid circular dependency
    from app.services.entity_extractor import EntityExtractor

    return EntityExtractor()


@lru_cache()
def get_file_handler():
    """Get file handler instance with text repository."""
    # Import here to avoid circular dependency
    from app.services.file_handler import FileHandler

    return FileHandler(text_repository=get_text_repository())


@lru_cache()
def get_ner_model_config() -> NERModelConfiguration:
    return NERModelConfiguration()
