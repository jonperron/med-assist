# pylint: disable=W0621
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import UploadFile
from io import BytesIO
from docx import Document as DocxDocument

from app.services.text_extractor import TextExtractor


@pytest.fixture
def text_extractor():
    return TextExtractor()


@pytest.mark.asyncio
async def test_extract_text_from_pdf(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.return_value = b"pdf content"

    with patch("app.services.text_extractor.fitz.open") as mock_fitz_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Text from PDF."
        mock_doc.__enter__.return_value = [mock_page]
        mock_fitz_open.return_value = mock_doc

        text = await text_extractor.extract_text(mock_file)
        assert text == "Text from PDF."
        mock_fitz_open.assert_called_once()


@pytest.mark.asyncio
async def test_extract_text_from_docx(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # Create a real DOCX in-memory file
    document = DocxDocument()
    document.add_paragraph("Text from DOCX.")
    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    mock_file.read.return_value = file_stream.read()

    text = await text_extractor.extract_text(mock_file)
    assert "Text from DOCX." in text


@pytest.mark.asyncio
async def test_extract_text_from_plaintext(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "text/plain"
    mock_file.read.return_value = b"Text from plain file."

    text = await text_extractor.extract_text(mock_file)
    assert text == "Text from plain file."


@pytest.mark.asyncio
async def test_unsupported_file_type(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/zip"
    mock_file.read.return_value = b"some data"

    with pytest.raises(ValueError, match="Unsupported file type"):
        await text_extractor.extract_text(mock_file)


@pytest.mark.asyncio
async def test_extraction_error(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.side_effect = Exception("Test error")

    with pytest.raises(ValueError, match="Error extracting text: Test error"):
        await text_extractor.extract_text(mock_file)
