# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.use_cases.read_entities import read_stored_entities
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.schemas.extraction import EntityDetail

FILE_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def mock_text_repository():
    return MagicMock(spec=TextRepositoryInterface)


@pytest.mark.asyncio
async def test_read_stored_entities(mock_text_repository):
    stored = {
        "pathologies": [
            EntityDetail(text="grippe", label="B-pathologie", score=0.95),
        ],
        "symptoms": [],
    }
    mock_text_repository.get_entities = AsyncMock(return_value=stored)

    result = await read_stored_entities(FILE_ID, mock_text_repository)

    mock_text_repository.get_entities.assert_called_once_with(FILE_ID)
    assert result == stored


@pytest.mark.asyncio
async def test_read_stored_entities_missing_document(mock_text_repository):
    mock_text_repository.get_entities = AsyncMock(return_value=None)

    assert await read_stored_entities(FILE_ID, mock_text_repository) is None


@pytest.mark.asyncio
async def test_read_stored_entities_never_reads_the_document_text(
    mock_text_repository,
):
    # Reading a document must not need its text, which is usually not stored.
    mock_text_repository.get_entities = AsyncMock(return_value={})
    mock_text_repository.get_text = AsyncMock()

    await read_stored_entities(FILE_ID, mock_text_repository)

    mock_text_repository.get_text.assert_not_called()
