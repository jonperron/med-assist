# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.use_cases.extract_entities import extract_entities
from app.repositories.text_repository import TextRepositoryInterface
from app.services.entity_extractor import EntityExtractor


@pytest.mark.asyncio
async def test_extract_entities():
    # Mock dependencies
    mock_text_repository = MagicMock(spec=TextRepositoryInterface)
    mock_entity_extractor = MagicMock(spec=EntityExtractor)

    file_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    text = "Le patient a la grippe."
    mock_text_repository.get_text = AsyncMock(return_value=text)

    expected_entities = {"diseases": ["grippe"], "symptoms": [], "treatments": []}
    mock_entity_extractor.extract_entities.return_value = expected_entities

    result = await extract_entities(
        file_id=file_id,
        text_repository=mock_text_repository,
        entity_extractor=mock_entity_extractor,
    )

    # Verify the file_id was passed as UUID
    mock_text_repository.get_text.assert_called_once_with(file_id)
    mock_entity_extractor.extract_entities.assert_called_once_with(text)
    assert result == expected_entities


@pytest.mark.asyncio
async def test_extract_entities_no_text():
    # Mock dependencies
    mock_text_repository = MagicMock(spec=TextRepositoryInterface)
    mock_entity_extractor = MagicMock(spec=EntityExtractor)

    file_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    mock_text_repository.get_text = AsyncMock(return_value=None)

    result = await extract_entities(
        file_id=file_id,
        text_repository=mock_text_repository,
        entity_extractor=mock_entity_extractor,
    )

    # Verify the file_id was passed as UUID
    mock_text_repository.get_text.assert_called_once_with(file_id)
    mock_entity_extractor.extract_entities.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_extract_entities_invalid_uuid():
    # Mock dependencies
    mock_text_repository = MagicMock(spec=TextRepositoryInterface)
    mock_entity_extractor = MagicMock(spec=EntityExtractor)

    file_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    text = "Some text."
    mock_text_repository.get_text = AsyncMock(return_value=text)

    expected_entities = {"diseases": [], "symptoms": [], "treatments": []}
    mock_entity_extractor.extract_entities.return_value = expected_entities

    result = await extract_entities(
        file_id=file_id,
        text_repository=mock_text_repository,
        entity_extractor=mock_entity_extractor,
    )

    # Should use the UUID directly
    mock_text_repository.get_text.assert_called_once_with(file_id)
    mock_entity_extractor.extract_entities.assert_called_once_with(text)
    assert result == expected_entities
