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
from app.services.pseudonymizer import Pseudonymizer
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
    """Get entity extractor instance."""
    return EntityExtractor(model_name=get_ner_model_config().model_name)


@lru_cache()
def get_text_extractor() -> TextExtractor:
    """Get text extractor instance."""
    return TextExtractor()


@lru_cache()
def get_pseudonymizer() -> Pseudonymizer:
    """Get pseudonymizer instance."""
    return Pseudonymizer()


@lru_cache()
def get_file_handler() -> FileHandler:
    """Get file handler instance with text repository."""
    return FileHandler(
        text_repository=get_text_repository(),
        entity_extractor=get_entity_extractor(),
        privacy_config=get_privacy_config(),
        pseudonymizer=get_pseudonymizer(),
    )
