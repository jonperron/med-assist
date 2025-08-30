# pylint: disable=W0621
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile

from app.services.file_handler import FileHandler
from app.repositories.text_repository import TextRepositoryInterface


@pytest.fixture
def mock_upload_file():
    mock = MagicMock(spec=UploadFile)
    mock.filename = "test.pdf"
    mock.read = AsyncMock(return_value=b"file content")
    return mock


@pytest.fixture
def mock_text_repository():
    mock = MagicMock(spec=TextRepositoryInterface)
    mock.save_text = AsyncMock()
    mock.save_batch = AsyncMock()
    return mock


@patch("app.services.file_handler.TextExtractor")
def test_file_handler_init(MockTextExtractor, mock_text_repository):
    handler = FileHandler(text_repository=mock_text_repository)
    MockTextExtractor.assert_called_once()
    assert handler.extractor is not None
    assert handler.text_repository is not None


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_success(
    MockTextExtractor, mock_text_repository, mock_upload_file
):
    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text = AsyncMock(return_value="extracted text")
    handler = FileHandler(text_repository=mock_text_repository)
    file_uuid = uuid4()
    result = await handler.process_file(file_uuid, mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_text_repository.save_text.assert_called_once_with(file_uuid, "extracted text")
    assert result is True


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_no_text(
    MockTextExtractor, mock_text_repository, mock_upload_file
):
    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text = AsyncMock(return_value=None)
    handler = FileHandler(text_repository=mock_text_repository)
    file_id = uuid4()
    result = await handler.process_file(file_id, mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_text_repository.save_text.assert_not_called()
    assert result is False


@pytest.mark.asyncio
async def test_file_handler_process_batch_success(mock_text_repository):
    batch_id = uuid4()
    file_ids = ["file1", "file2", "file3"]

    handler = FileHandler(text_repository=mock_text_repository)
    result = await handler.process_batch(batch_id, file_ids)
    mock_text_repository.save_batch.assert_called_once_with(batch_id, file_ids)
    assert result is True


@pytest.mark.asyncio
async def test_file_handler_process_batch_failure(mock_text_repository):
    batch_id = uuid4()
    file_ids = ["file1", "file2"]

    # Mock save_batch to raise an exception
    mock_text_repository.save_batch = AsyncMock(side_effect=Exception("Save failed"))

    handler = FileHandler(text_repository=mock_text_repository)

    with pytest.raises(Exception):
        await handler.process_batch(batch_id, file_ids)
