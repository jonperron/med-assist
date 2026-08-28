from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NERModelConfiguration(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    model_name: str = Field(..., alias="NER_MODEL_NAME")
    inference_threads: int = Field(
        default=0,
        alias="NER_INFERENCE_THREADS",
        ge=0,
        description=(
            "Threads torch may use for one CPU inference. Zero keeps torch's "
            "own default, which is one thread per core."
        ),
    )
    max_concurrent_inferences: int = Field(
        default=1,
        alias="NER_MAX_CONCURRENT_INFERENCES",
        gt=0,
        le=8,
        description=(
            "How many documents may be inside the model at once. One by "
            "default: a second copy of the activations is what puts a small "
            "machine into swap. Above one, the same transformers pipeline is "
            "called from several threads, which transformers does not document "
            "as safe - prefer more worker processes. Bounded because the "
            "threadpool behind it has a ceiling of its own."
        ),
    )
