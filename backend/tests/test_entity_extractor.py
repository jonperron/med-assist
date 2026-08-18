# pylint: disable=W0621
import ast
import asyncio
import inspect
import logging
import threading

import pytest
from unittest.mock import MagicMock, patch, mock_open
from app.services.entity_extractor import entity_extractor as entity_extractor_module
from app.services.entity_extractor import EntityExtractor
from app.schemas.extraction import EntityDetail


@pytest.fixture
def mock_ner_pipeline():
    with patch(
        "app.services.entity_extractor.entity_extractor.pipeline"
    ) as mock_pipeline:
        yield mock_pipeline


def build_extractor(mock_label_mapping, **kwargs):
    """An extractor over a mocked pipeline and the test label table."""
    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            return EntityExtractor(model_name="Dummy/Model", **kwargs)


@pytest.fixture
def mock_label_mapping():
    """Mock label mapping JSON content"""
    return {
        "language": "fr",
        "dataset": "test_clinical",
        "description": "Test mapping",
        "categories": {
            "diseases": {
                "description": "Diseases",
                "labels": ["pathologie", "maladie"],
            },
            "symptoms": {"description": "Symptoms", "labels": ["symptom", "sosy"]},
            "treatments": {
                "description": "Treatments",
                "labels": ["treatment", "traitement"],
            },
        },
    }


def test_entity_extractor_init(mock_ner_pipeline, mock_label_mapping):
    extractor = build_extractor(mock_label_mapping)

    mock_ner_pipeline.assert_called_once_with(
        "ner", model="Dummy/Model", aggregation_strategy="max", device="cpu"
    )
    assert extractor.ner_pipeline is not None


def test_the_model_is_pinned_to_the_cpu(mock_ner_pipeline, mock_label_mapping):
    # The runtime installs the CPU build of torch, so this is what would happen
    # anyway. Saying it means a host that happens to carry an accelerator does
    # not silently start copying clinical text onto it.
    build_extractor(mock_label_mapping)

    assert mock_ner_pipeline.call_args.kwargs["device"] == "cpu"


def test_the_default_thread_count_is_left_to_torch(
    mock_ner_pipeline, mock_label_mapping
):
    with patch.object(entity_extractor_module.torch, "set_num_threads") as set_threads:
        build_extractor(mock_label_mapping)

    set_threads.assert_not_called()


def test_a_configured_thread_count_reaches_torch(mock_ner_pipeline, mock_label_mapping):
    with patch.object(entity_extractor_module.torch, "set_num_threads") as set_threads:
        build_extractor(mock_label_mapping, inference_threads=2)

    set_threads.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_inference_never_runs_on_the_event_loop(
    mock_ner_pipeline, mock_label_mapping
):
    # A synchronous model awaited from the loop holds every other request -
    # including the health check - for the length of the document.
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    threads = []

    def record_the_thread(text):
        threads.append(threading.current_thread())
        return []

    mock_pipeline_instance.side_effect = record_the_thread
    extractor = build_extractor(mock_label_mapping)

    await extractor.extract_entities("Le patient va bien.")

    assert threads and threads[0] is not threading.current_thread()


@pytest.mark.asyncio
async def test_one_document_is_in_the_model_at_a_time_by_default(
    mock_ner_pipeline, mock_label_mapping
):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    lock = threading.Lock()
    in_flight = 0
    peak = 0

    def run_slowly(text):
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        threading.Event().wait(0.05)
        with lock:
            in_flight -= 1
        return []

    mock_pipeline_instance.side_effect = run_slowly
    extractor = build_extractor(mock_label_mapping)

    await asyncio.gather(*(extractor.extract_entities("texte") for _ in range(4)))

    # Peak memory is then a function of the largest document, not of how many
    # arrived together - which is what makes the small-hardware claim hold.
    assert peak == 1


@pytest.mark.asyncio
async def test_the_deployment_can_widen_the_concurrency(
    mock_ner_pipeline, mock_label_mapping
):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    # Both halves have to be inside the model together for this to return.
    both_arrived = threading.Barrier(2, timeout=5)

    def wait_for_the_other(text):
        both_arrived.wait()
        return []

    mock_pipeline_instance.side_effect = wait_for_the_other
    extractor = build_extractor(mock_label_mapping, max_concurrent_inferences=2)

    await asyncio.gather(*(extractor.extract_entities("texte") for _ in range(2)))

    assert not both_arrived.broken


@pytest.mark.asyncio
async def test_a_failed_inference_gives_its_slot_back(
    mock_ner_pipeline, mock_label_mapping
):
    # The slot is released by `async with`. A refactor to a manual acquire that
    # forgets the failure path deadlocks every later request instead.
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    mock_pipeline_instance.side_effect = RuntimeError("the model gave up")
    extractor = build_extractor(mock_label_mapping)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await extractor.extract_entities("texte")

    mock_pipeline_instance.side_effect = None
    mock_pipeline_instance.return_value = []
    assert await extractor.extract_entities("texte") is not None


def test_one_extractor_serves_more_than_one_event_loop(
    mock_ner_pipeline, mock_label_mapping
):
    # The extractor is an lru_cache singleton. asyncio's semaphore binds itself
    # to the loop that first awaits it and raises on the second one, which is
    # why this uses anyio's.
    mock_pipeline_instance = MagicMock(return_value=[])
    mock_ner_pipeline.return_value = mock_pipeline_instance
    extractor = build_extractor(mock_label_mapping)

    for _ in range(2):
        asyncio.run(extractor.extract_entities("texte"))

    assert mock_pipeline_instance.call_count == 2


def test_extract_entities_detailed(mock_ner_pipeline, mock_label_mapping):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance

    mock_pipeline_instance.return_value = [
        {
            "entity_group": "B-pathologie",
            "word": "grippe",
            "score": 0.95,
            "start": 16,
            "end": 22,
        },
        {
            "entity_group": "B-sosy",
            "word": "fièvre",
            "score": 0.92,
            "start": 34,
            "end": 40,
        },
        {
            "entity_group": "B-traitement",
            "word": "paracétamol",
            "score": 0.88,
            "start": 57,
            "end": 68,
        },
    ]

    extractor = build_extractor(mock_label_mapping)
    text = "Le patient a la grippe avec de la fièvre, traité avec du paracétamol."

    entities = extractor.run_inference(text)

    # Check that entities are EntityDetail instances
    assert len(entities["diseases"]) == 1
    assert isinstance(entities["diseases"][0], EntityDetail)
    assert entities["diseases"][0].text == "grippe"
    assert entities["diseases"][0].score == 0.95

    assert len(entities["symptoms"]) == 1
    assert isinstance(entities["symptoms"][0], EntityDetail)
    assert entities["symptoms"][0].text == "fièvre"

    assert len(entities["treatments"]) == 1
    assert isinstance(entities["treatments"][0], EntityDetail)
    assert entities["treatments"][0].text == "paracétamol"

    mock_pipeline_instance.assert_called_once_with(text)


@pytest.mark.asyncio
async def test_extract_entities_returns_what_the_model_found(
    mock_ner_pipeline, mock_label_mapping
):
    # The same result, through the coroutine callers actually use.
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    mock_pipeline_instance.return_value = [
        {
            "entity_group": "B-sosy",
            "word": "fièvre",
            "score": 0.92,
            "start": 3,
            "end": 9,
        }
    ]
    extractor = build_extractor(mock_label_mapping)

    entities = await extractor.extract_entities("Le fièvre")

    assert entities["symptoms"][0].text == "fièvre"


def test_extract_entities_no_entities(mock_ner_pipeline, mock_label_mapping):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    mock_pipeline_instance.return_value = []
    extractor = build_extractor(mock_label_mapping)
    text = "Le patient va bien."

    entities = extractor.run_inference(text)

    assert entities["diseases"] == []
    assert entities["symptoms"] == []
    assert entities["treatments"] == []
    mock_pipeline_instance.assert_called_once_with(text)


def test_get_available_categories(mock_ner_pipeline, mock_label_mapping):
    categories = build_extractor(mock_label_mapping).get_available_categories()

    assert "diseases" in categories
    assert "symptoms" in categories
    assert "treatments" in categories
    assert categories["diseases"] == "Diseases"


def test_get_mapping_info(mock_ner_pipeline, mock_label_mapping):
    info = build_extractor(mock_label_mapping).get_mapping_info()

    assert info["language"] == "fr"
    assert info["dataset"] == "test_clinical"
    assert info["description"] == "Test mapping"


def test_the_extractor_never_imports_the_application_wiring():
    # app.core.dependencies builds the extractor. An extractor that imports it
    # back closes a loop, and the loop is what forced dependencies.py to hide
    # its imports inside function bodies.
    tree = ast.parse(inspect.getsource(entity_extractor_module))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.core.dependencies" not in imported


@pytest.fixture
def extractor(mock_ner_pipeline, mock_label_mapping):
    return build_extractor(mock_label_mapping)


@pytest.mark.parametrize(
    "label, category",
    [
        ("pathologie", "diseases"),
        ("B-pathologie", "diseases"),
        ("I-sosy", "symptoms"),
        ("TRAITEMENT", "treatments"),
    ],
)
def test_categorize_entity_reads_the_label_table(extractor, label, category):
    assert extractor.categorize_entity(label) == category


@pytest.mark.parametrize("label", ["pathologies", "traitements", "symptomatique"])
def test_a_word_that_merely_contains_a_known_label_is_not_that_category(
    extractor, label
):
    # Substring matching categorised anything containing "dose" as a dose.
    assert extractor.categorize_entity(label) == "other"


@pytest.mark.parametrize("label", ["sous-traitement", "b-traitement_x", "traitement 2"])
def test_a_compound_label_is_matched_part_by_part(extractor, label):
    # A part of a compound label is a label; a fragment of a word is not.
    assert extractor.categorize_entity(label) == "treatments"


def test_only_the_bio_prefix_is_stripped(extractor, mock_label_mapping):
    # "symptom" survives intact; a blanket replace of "b-"/"i-" would not have
    # touched it either, but it would have turned "sosy-b-x" into "sosyx".
    mock_label_mapping["categories"]["symptoms"]["labels"].append("sosy-b-x")
    extractor.categories = extractor.build_category_lookup()

    assert extractor.categorize_entity("B-sosy-b-x") == "symptoms"


def fast_tokenizer(model_max_length=512):
    """A stand-in for the tokenizer the pipeline exposes."""
    tokenizer = MagicMock()
    tokenizer.is_fast = True
    tokenizer.model_max_length = model_max_length
    return tokenizer


@pytest.mark.asyncio
async def test_a_long_document_is_read_through_a_sliding_window(
    mock_ner_pipeline, mock_label_mapping
):
    # Without a stride the pipeline reads the first window and drops the rest,
    # so a discharge summary loses its tail and the response looks complete.
    mock_pipeline_instance = MagicMock(return_value=[])
    mock_pipeline_instance.tokenizer = fast_tokenizer()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    extractor = build_extractor(mock_label_mapping)

    await extractor.extract_entities("texte")

    # A quarter of the window: an entity lying across a boundary stays whole in
    # one of the two chunks it appears in.
    assert mock_pipeline_instance.call_args.kwargs["stride"] == 128


@pytest.mark.parametrize(
    "is_fast, model_max_length",
    [
        # transformers refuses a stride on a slow tokenizer.
        (False, 512),
        # The sentinel a tokenizer uses for "no limit": no window to slide.
        (True, 1000000000000000019884624838656),
        (True, 0),
    ],
)
@pytest.mark.asyncio
async def test_the_window_is_left_alone_when_it_cannot_be_slid(
    mock_ner_pipeline, mock_label_mapping, is_fast, model_max_length
):
    mock_pipeline_instance = MagicMock(return_value=[])
    mock_pipeline_instance.tokenizer = fast_tokenizer(model_max_length)
    mock_pipeline_instance.tokenizer.is_fast = is_fast
    mock_ner_pipeline.return_value = mock_pipeline_instance
    extractor = build_extractor(mock_label_mapping)

    await extractor.extract_entities("texte")

    assert "stride" not in mock_pipeline_instance.call_args.kwargs


def test_silent_truncation_is_reported_at_load_time(
    mock_ner_pipeline, mock_label_mapping, caplog
):
    # Truncation cannot be seen in the response, so the log is the only place a
    # deployment learns it is losing the end of every long document.
    mock_pipeline_instance = MagicMock(return_value=[])
    mock_pipeline_instance.tokenizer = fast_tokenizer()
    mock_pipeline_instance.tokenizer.is_fast = False
    mock_ner_pipeline.return_value = mock_pipeline_instance

    with caplog.at_level(logging.WARNING):
        build_extractor(mock_label_mapping)

    assert "truncated" in caplog.text


def test_a_sliding_window_is_not_announced(
    mock_ner_pipeline, mock_label_mapping, caplog
):
    mock_pipeline_instance = MagicMock(return_value=[])
    mock_pipeline_instance.tokenizer = fast_tokenizer()
    mock_ner_pipeline.return_value = mock_pipeline_instance

    with caplog.at_level(logging.WARNING):
        build_extractor(mock_label_mapping)

    assert "truncated" not in caplog.text
