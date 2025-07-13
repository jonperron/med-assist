# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.use_cases.extract_entities import extract_entities


@pytest.fixture
def mock_redis_storage():
    mock = MagicMock()
    mock.get_value = AsyncMock()
    return mock


@pytest.fixture
def mock_entity_extractor():
    mock = MagicMock()
    mock.extract_entities = MagicMock()
    return mock


@pytest.mark.asyncio
@patch("app.use_cases.extract_entities.get_redis_storage")
@patch("app.use_cases.extract_entities.EntityExtractor")
async def test_extract_entities(
    MockEntityExtractor,
    mock_get_redis_storage,
    mock_redis_storage,
    mock_entity_extractor,
):
    mock_get_redis_storage.return_value = mock_redis_storage
    MockEntityExtractor.return_value = mock_entity_extractor

    file_id = "test_file_id"
    text = "Le patient a la grippe."
    mock_redis_storage.get_value.return_value = text

    expected_entities = {"diseases": ["grippe"], "symptoms": [], "treatments": []}
    mock_entity_extractor.extract_entities.return_value = expected_entities

    result = await extract_entities(file_id)

    mock_redis_storage.get_value.assert_called_once_with(file_id)
    mock_entity_extractor.extract_entities.assert_called_once_with(text)
    assert result == expected_entities


@pytest.mark.asyncio
@patch("app.use_cases.extract_entities.get_redis_storage")
@patch("app.use_cases.extract_entities.EntityExtractor")
async def test_extract_entities_no_text(
    MockEntityExtractor,
    mock_get_redis_storage,
    mock_redis_storage,
    mock_entity_extractor,
):
    mock_get_redis_storage.return_value = mock_redis_storage
    MockEntityExtractor.return_value = mock_entity_extractor

    file_id = "test_file_id"
    mock_redis_storage.get_value.return_value = None

    result = await extract_entities(file_id)

    mock_redis_storage.get_value.assert_called_once_with(file_id)
    mock_entity_extractor.extract_entities.assert_not_called()
    assert result is None
