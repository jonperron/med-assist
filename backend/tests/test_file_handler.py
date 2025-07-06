import pytest
from unittest.mock import MagicMock, patch
from fastapi import UploadFile

from app.use_cases.file_handler import FileHandler


@pytest.fixture
def mock_upload_file():
    mock = MagicMock(spec=UploadFile)
    mock.filename = "test.pdf"
    mock.read = MagicMock(return_value=b"file content")
    return mock


@pytest.fixture
def mock_redis_storage():
    return MagicMock()


@patch('app.use_cases.file_handler.TextExtractor')
def test_file_handler_init(MockTextExtractor, mock_redis_storage):
    handler = FileHandler(redis_storage=mock_redis_storage)
    MockTextExtractor.assert_called_once()
    assert handler.extractor is not None
    assert handler.storage is not None


@patch('app.use_cases.file_handler.TextExtractor')
def test_save_extracted_text(MockTextExtractor, mock_redis_storage):
    handler = FileHandler(redis_storage=mock_redis_storage)
    handler.save_extracted_text("test.pdf", "extracted text")
    mock_redis_storage.store_value.assert_called_once_with("test.pdf", "extracted text")


@pytest.mark.asyncio
@patch('app.use_cases.file_handler.TextExtractor')
async def test_extract_text(MockTextExtractor, mock_redis_storage, mock_upload_file):
    async def async_return(value):
        return value

    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text.return_value = async_return("extracted text")
    handler = FileHandler(redis_storage=mock_redis_storage)
    result = await handler.extract_text(mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_redis_storage.store_value.assert_called_once_with("test.pdf", "extracted text")
    assert result is True


@pytest.mark.asyncio
@patch('app.use_cases.file_handler.TextExtractor')
async def test_extract_text_no_text(MockTextExtractor, mock_redis_storage, mock_upload_file):
    async def async_return(value):
        return value
        
    mock_extractor_instance = MockTextExtractor.return_value
    mock_extractor_instance.extract_text.return_value = async_return(None)
    handler = FileHandler(redis_storage=mock_redis_storage)
    result = await handler.extract_text(mock_upload_file)
    mock_extractor_instance.extract_text.assert_called_once_with(mock_upload_file)
    mock_redis_storage.store_value.assert_called_once_with("test.pdf", None)
    assert result is False