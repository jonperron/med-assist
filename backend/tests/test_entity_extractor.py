# pylint: disable=W0621
import pytest
from unittest.mock import MagicMock, patch, mock_open
from app.services.entity_extractor import EntityExtractor
from app.schemas.extraction import EntityDetail


@pytest.fixture
def mock_ner_pipeline():
    with patch(
        "app.services.entity_extractor.entity_extractor.pipeline"
    ) as mock_pipeline:
        yield mock_pipeline


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
    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            extractor = EntityExtractor(model_name="Dummy/Model")
            mock_ner_pipeline.assert_called_once_with(
                "ner", model="Dummy/Model", aggregation_strategy="simple"
            )
            assert extractor.ner_pipeline is not None


def test_extract_entities_detailed(mock_ner_pipeline, mock_label_mapping):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance

    mock_pipeline_instance.return_value = [
        {
            "entity_group": "B-pathologie",
            "word": "grippe",
            "score": 0.95,
            "start": 0,
            "end": 6,
        },
        {
            "entity_group": "B-sosy",
            "word": "fièvre",
            "score": 0.92,
            "start": 7,
            "end": 13,
        },
        {
            "entity_group": "B-traitement",
            "word": "paracétamol",
            "score": 0.88,
            "start": 14,
            "end": 25,
        },
    ]

    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            extractor = EntityExtractor(model_name="Dummy/Model")
            text = (
                "Le patient a la grippe avec de la fièvre, traité avec du paracétamol."
            )
            entities = extractor.extract_entities(text)

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


def test_extract_entities_no_entities(mock_ner_pipeline, mock_label_mapping):
    mock_pipeline_instance = MagicMock()
    mock_ner_pipeline.return_value = mock_pipeline_instance
    mock_pipeline_instance.return_value = []

    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            extractor = EntityExtractor(model_name="Dummy/Model")
            text = "Le patient va bien."
            entities = extractor.extract_entities(text)

            assert entities["diseases"] == []
            assert entities["symptoms"] == []
            assert entities["treatments"] == []
            mock_pipeline_instance.assert_called_once_with(text)


def test_get_available_categories(mock_ner_pipeline, mock_label_mapping):
    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            extractor = EntityExtractor(model_name="Dummy/Model")
            categories = extractor.get_available_categories()

            assert "diseases" in categories
            assert "symptoms" in categories
            assert "treatments" in categories
            assert categories["diseases"] == "Diseases"


def test_get_mapping_info(mock_ner_pipeline, mock_label_mapping):
    with patch("builtins.open", mock_open(read_data=str(mock_label_mapping))):
        with patch("json.load", return_value=mock_label_mapping):
            extractor = EntityExtractor(model_name="Dummy/Model")
            info = extractor.get_mapping_info()

            assert info["language"] == "fr"
            assert info["dataset"] == "test_clinical"
            assert info["description"] == "Test mapping"
