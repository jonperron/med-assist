# pylint: disable=W0621
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from app.db.redis import RedisStorage
from app.repositories.text_repository import RedisTextRepository


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
    mock_storage.store_value.assert_called_once_with(str(file_id), "extracted text")


@pytest.mark.asyncio
async def test_get_text(repository, mock_storage):
    file_id = uuid4()
    assert await repository.get_text(file_id) == "extracted text"
    mock_storage.get_value.assert_called_once_with(str(file_id))


@pytest.mark.asyncio
async def test_get_text_ttl(repository, mock_storage):
    file_id = uuid4()
    assert await repository.get_text_ttl(file_id) == 1800
    mock_storage.get_ttl.assert_called_once_with(str(file_id))


@pytest.mark.asyncio
async def test_get_text_ttl_expired(repository, mock_storage):
    mock_storage.get_ttl.return_value = None
    assert await repository.get_text_ttl(uuid4()) is None


@pytest.mark.asyncio
async def test_delete_text(repository, mock_storage):
    file_id = uuid4()
    assert await repository.delete_text(file_id) is True
    mock_storage.delete_value.assert_called_once_with(str(file_id))


@pytest.mark.asyncio
async def test_delete_text_missing_document(repository, mock_storage):
    mock_storage.delete_value.return_value = False
    assert await repository.delete_text(uuid4()) is False


@pytest.mark.asyncio
async def test_save_batch(repository, mock_storage):
    batch_id = uuid4()
    file_ids = [str(uuid4())]
    await repository.save_batch(batch_id, file_ids)
    mock_storage.store_value.assert_called_once_with(str(batch_id), str(file_ids))
