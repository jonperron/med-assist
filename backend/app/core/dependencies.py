from functools import lru_cache

from app.core.config import (
    NERModelConfiguration,
    PrivacyConfiguration,
    RedisConfiguration,
)
from app.db.redis import RedisStorage
from app.repositories.text_repository import (
    RedisTextRepository,
    TextRepositoryInterface,
)
from app.services.entity_extractor import EntityExtractor
from app.services.file_handler import FileHandler
from app.services.text_extractor import TextExtractor


@lru_cache()
def get_redis_config() -> RedisConfiguration:
    return RedisConfiguration()


@lru_cache()
def get_privacy_config() -> PrivacyConfiguration:
    return PrivacyConfiguration()


@lru_cache()
def get_ner_model_config() -> NERModelConfiguration:
    return NERModelConfiguration()


@lru_cache()
def get_redis_storage() -> RedisStorage:
    return RedisStorage(config=get_redis_config())


@lru_cache()
def get_text_repository() -> TextRepositoryInterface:
    """Get text repository instance."""
    return RedisTextRepository(redis_storage=get_redis_storage())


@lru_cache()
def get_entity_extractor() -> EntityExtractor:
    """Get entity extractor instance.

    Building one loads the model weights, which takes seconds. The cache means
    that happens once per process; the lifespan handler in `main` pays it at
    startup so no caller does.
    """
    config = get_ner_model_config()
    return EntityExtractor(
        model_name=config.model_name,
        inference_threads=config.inference_threads,
        max_concurrent_inferences=config.max_concurrent_inferences,
    )


@lru_cache()
def get_text_extractor() -> TextExtractor:
    """Get text extractor instance."""
    return TextExtractor()


@lru_cache()
def get_file_handler() -> FileHandler:
    """Get file handler instance with text repository."""
    return FileHandler(
        text_repository=get_text_repository(),
        entity_extractor=get_entity_extractor(),
        privacy_config=get_privacy_config(),
    )
