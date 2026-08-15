# pylint: disable=W0621
import json

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.db.redis import RedisStorage
from app.repositories.text_repository import RedisTextRepository
from app.schemas.extraction import EntityDetail


@pytest.fixture
def mock_storage():
    storage = MagicMock(spec=RedisStorage)
    storage.store_value = AsyncMock()
    storage.get_value = AsyncMock(return_value="extracted text")
    storage.get_ttl = AsyncMock(return_value=1800)
    storage.delete_value = AsyncMock(return_value=True)
    return storage


@pytest.fixture
def repository(mock_storage):
    return RedisTextRepository(redis_storage=mock_storage)


@pytest.mark.asyncio
async def test_save_text(repository, mock_storage):
    file_id = uuid4()
    await repository.save_text(file_id, "extracted text")
    mock_storage.store_value.assert_called_once_with(
        f"doc:{file_id}:text", "extracted text"
    )


@pytest.mark.asyncio
async def test_get_text(repository, mock_storage):
    file_id = uuid4()
    assert await repository.get_text(file_id) == "extracted text"
    mock_storage.get_value.assert_called_once_with(f"doc:{file_id}:text")


@pytest.mark.asyncio
async def test_save_entities_serializes_every_category(repository, mock_storage):
    file_id = uuid4()
    entities = {
        "pathologies": [
            EntityDetail(text="grippe", label="pathologie", score=0.9, start=3, end=9)
        ],
        "symptoms": [],
    }

    await repository.save_entities(file_id, entities)

    key, payload = mock_storage.store_value.call_args.args
    assert key == f"doc:{file_id}:entities"
    assert json.loads(payload) == {
        "pathologies": [
            {
                "text": "grippe",
                "label": "pathologie",
                "score": 0.9,
                "start": 3,
                "end": 9,
            }
        ],
        "symptoms": [],
    }


@pytest.mark.asyncio
async def test_get_entities(repository, mock_storage):
    file_id = uuid4()
    mock_storage.get_value.return_value = json.dumps(
        {"pathologies": [{"text": "grippe", "label": "pathologie", "score": 0.9}]}
    )

    entities = await repository.get_entities(file_id)

    mock_storage.get_value.assert_called_once_with(f"doc:{file_id}:entities")
    assert entities == {
        "pathologies": [
            EntityDetail(text="grippe", label="pathologie", score=0.9),
        ]
    }
    assert entities["pathologies"][0].start is None


@pytest.mark.asyncio
async def test_get_entities_missing_document(repository, mock_storage):
    mock_storage.get_value.return_value = None
    assert await repository.get_entities(uuid4()) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", ["not json", json.dumps({"symptoms": [{"a": 1}]})])
async def test_get_entities_unreadable_payload(
    repository, mock_storage, stored, caplog
):
    file_id = uuid4()
    mock_storage.get_value.return_value = stored

    assert await repository.get_entities(file_id) is None
    # The document is unreadable, but the log says so without quoting content.
    assert stored not in caplog.text


@pytest.mark.asyncio
async def test_get_document_ttl(repository, mock_storage):
    file_id = uuid4()
    assert await repository.get_document_ttl(file_id) == 1800
    mock_storage.get_ttl.assert_called_once_with(f"doc:{file_id}:entities")


@pytest.mark.asyncio
async def test_get_document_ttl_expired(repository, mock_storage):
    mock_storage.get_ttl.return_value = None
    assert await repository.get_document_ttl(uuid4()) is None


@pytest.mark.asyncio
async def test_delete_document_removes_text_and_entities(repository, mock_storage):
    file_id = uuid4()
    assert await repository.delete_document(file_id) is True
    mock_storage.delete_value.assert_called_once_with(
        f"doc:{file_id}:entities", f"doc:{file_id}:text"
    )


@pytest.mark.asyncio
async def test_delete_document_missing_document(repository, mock_storage):
    mock_storage.delete_value.return_value = False
    assert await repository.delete_document(uuid4()) is False
