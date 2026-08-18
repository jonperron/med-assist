"""The CPU knobs are the small-hardware story, so the defaults are asserted.

A typo in a field alias reverts the whole feature to its defaults without
failing anything, which is exactly the kind of decay these cover.
"""

# pylint: disable=W0621
import pytest
from pydantic import ValidationError

from app.core.config import NERModelConfiguration
from app.core.dependencies import get_entity_extractor


@pytest.fixture
def shipped_defaults(monkeypatch):
    # Neither the environment nor a local .env: this is about what ships.
    monkeypatch.delenv("NER_INFERENCE_THREADS", raising=False)
    monkeypatch.delenv("NER_MAX_CONCURRENT_INFERENCES", raising=False)
    return NERModelConfiguration(NER_MODEL_NAME="Dummy/Model", _env_file=None)


def test_the_thread_count_is_left_to_torch_by_default(shipped_defaults):
    assert shipped_defaults.inference_threads == 0


def test_one_document_is_in_the_model_at_a_time_by_default(shipped_defaults):
    assert shipped_defaults.max_concurrent_inferences == 1


@pytest.mark.parametrize(
    "variable, value, field",
    [
        ("NER_INFERENCE_THREADS", "4", "inference_threads"),
        ("NER_MAX_CONCURRENT_INFERENCES", "2", "max_concurrent_inferences"),
    ],
)
def test_the_environment_variable_reaches_the_field(
    monkeypatch, variable, value, field
):
    monkeypatch.setenv(variable, value)

    config = NERModelConfiguration(NER_MODEL_NAME="Dummy/Model", _env_file=None)

    assert getattr(config, field) == int(value)


@pytest.mark.parametrize(
    "variable, value",
    [
        ("NER_INFERENCE_THREADS", "-1"),
        ("NER_MAX_CONCURRENT_INFERENCES", "0"),
        # Above the threadpool's own ceiling the bound stops meaning anything.
        ("NER_MAX_CONCURRENT_INFERENCES", "64"),
    ],
)
def test_a_value_that_cannot_mean_anything_is_refused(monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        NERModelConfiguration(NER_MODEL_NAME="Dummy/Model", _env_file=None)


def test_the_configured_values_reach_the_extractor(monkeypatch):
    # Without this, both settings can be read correctly and dropped on the way
    # to the constructor, and every other test still passes.
    built = {}

    class RecordingExtractor:
        def __init__(self, **kwargs):
            built.update(kwargs)

    monkeypatch.setattr(
        "app.core.dependencies.EntityExtractor", RecordingExtractor, raising=True
    )
    monkeypatch.setattr(
        "app.core.dependencies.get_ner_model_config",
        lambda: NERModelConfiguration(
            NER_MODEL_NAME="Dummy/Model",
            NER_INFERENCE_THREADS=3,
            NER_MAX_CONCURRENT_INFERENCES=2,
            _env_file=None,
        ),
    )
    get_entity_extractor.cache_clear()
    try:
        get_entity_extractor()
    finally:
        get_entity_extractor.cache_clear()

    assert built == {
        "model_name": "Dummy/Model",
        "inference_threads": 3,
        "max_concurrent_inferences": 2,
    }
