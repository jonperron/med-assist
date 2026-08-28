from functools import lru_cache

from app.core.config import NERModelConfiguration
from app.services.entity_extractor import EntityExtractor
from app.services.text_extractor import TextExtractor


@lru_cache()
def get_ner_model_config() -> NERModelConfiguration:
    return NERModelConfiguration()


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
