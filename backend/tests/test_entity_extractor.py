# pylint: disable=W0621
import pytest
from unittest.mock import MagicMock, patch
from app.services.entity_extractor import EntityExtractor


@pytest.fixture
def mock_ner_pipeline():
    with patch("app.services.entity_extractor.pipeline") as mock_pipeline:
        yield mock_pipeline


def test_entity_extractor_init(mock_ner_pipeline):
    extractor = EntityExtractor()
    mock_ner_pipeline.assert_called_once_with(
        "ner", model="Jean-Baptiste/camembert-ner", aggregation_strategy="simple"
    )
    assert extractor.ner_pipeline is not None


def test_extract_entities(mock_ner_pipeline):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance

    mock_pipeline_instance.return_value = [
        {"entity_group": "maladie", "word": "grippe"},
        {"entity_group": "symptom", "word": "fièvre"},
        {"entity_group": "treatment", "word": "paracétamol"},
    ]

    extractor = EntityExtractor()
    text = "Le patient a la grippe avec de la fièvre, traité avec du paracétamol."
    entities = extractor.extract_entities(text)

    assert entities["diseases"] == ["grippe"]
    assert entities["symptoms"] == ["fièvre"]
    assert entities["treatments"] == ["paracétamol"]
    mock_pipeline_instance.assert_called_once_with(text)


def test_extract_entities_no_entities(mock_ner_pipeline):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    mock_pipeline_instance.return_value = []

    extractor = EntityExtractor()
    text = "Le patient va bien."
    entities = extractor.extract_entities(text)

    assert entities["diseases"] == []
    assert entities["symptoms"] == []
    assert entities["treatments"] == []
    mock_pipeline_instance.assert_called_once_with(text)
