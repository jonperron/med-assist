# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile
from uuid import uuid4

from app.services.file_handler import FileHandler


@pytest.fixture
def mock_upload_file():
    mock = MagicMock(spec=UploadFile)
    mock.filename = "test.pdf"
    mock.read = AsyncMock(return_value=b"file content")
    return mock


@pytest.fixture
def mock_redis_storage():
    mock = MagicMock()
    mock.store_value = AsyncMock()
    return mock


@patch("app.services.file_handler.TextExtractor")
def test_file_handler_init(MockTextExtractor, mock_redis_storage):
    handler = FileHandler(redis_storage=mock_redis_storage)
    MockTextExtractor.assert_called_once()
    assert handler.extractor is not None
    assert handler.storage is not None


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_save_extracted_text(MockTextExtractor, mock_redis_storage):
    handler = FileHandler(redis_storage=mock_redis_storage)
    file_uuid = uuid4()
    await handler.save_extracted_text(file_uuid, "extracted text")
    mock_redis_storage.store_value.assert_called_once_with(
        str(file_uuid), "extracted text"
    )


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_extract_text(MockTextExtractor, mock_redis_storage, mock_upload_file):
    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text = AsyncMock(return_value="extracted text")
    handler = FileHandler(redis_storage=mock_redis_storage)
    file_uuid = uuid4()
    result = await handler.extract_text(file_uuid, mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_redis_storage.store_value.assert_called_once_with(
        str(file_uuid), "extracted text"
    )
    assert result is True


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_extract_text_no_text(
    MockTextExtractor, mock_redis_storage, mock_upload_file
):
    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text = AsyncMock(return_value=None)
    handler = FileHandler(redis_storage=mock_redis_storage)
    file_id = uuid4()
    result = await handler.extract_text(file_id, mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_redis_storage.store_value.assert_not_called()
    assert result is False
