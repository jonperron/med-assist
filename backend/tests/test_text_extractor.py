# pylint: disable=W0621
import time
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
async def test_pdf_pages_are_separated_and_page_numbers_dropped(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.return_value = b"pdf content"

    with patch("app.services.text_extractor.fitz.open") as mock_fitz_open:
        first, second = MagicMock(), MagicMock()
        first.get_text.return_value = "Culture negative\nPage : 1 / 2\n"
        second.get_text.return_value = "Kyste branchial\nPage 2 sur 2"
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = [first, second]
        mock_fitz_open.return_value = mock_doc

        text = await text_extractor.extract_text(mock_file)

    assert text == "Culture negative\n\nKyste branchial\n"


@pytest.mark.asyncio
async def test_docx_table_rows_are_kept_one_per_line(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = DocxDocument()
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Polynucleaires"
    table.rows[0].cells[1].text = "Tres nombreux"
    file_stream = BytesIO()
    document.save(file_stream)
    mock_file.read.return_value = file_stream.getvalue()

    text = await text_extractor.extract_text(mock_file)

    assert "Polynucleaires : Tres nombreux" in text


@pytest.mark.asyncio
async def test_docx_merged_cell_is_emitted_once_and_repeats_are_kept(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = DocxDocument()
    table = document.add_table(rows=20, cols=2)
    table.cell(0, 0).merge(table.cell(19, 0))
    table.cell(0, 0).text = "Prelevement"
    for index in range(20):
        table.cell(index, 1).text = "Negatif"
    file_stream = BytesIO()
    document.save(file_stream)
    mock_file.read.return_value = file_stream.getvalue()

    text = await text_extractor.extract_text(mock_file)

    assert text.count("Prelevement") == 1
    assert text.count("Negatif") == 20


@pytest.mark.asyncio
async def test_page_number_regex_does_not_stall_on_long_whitespace(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.return_value = b"pdf content"

    with patch("app.services.text_extractor.fitz.open") as mock_fitz_open:
        page = MagicMock()
        page.get_text.return_value = "Page" + " " * 200_000 + "x"
        mock_doc = MagicMock()
        mock_doc.__enter__.return_value = [page]
        mock_fitz_open.return_value = mock_doc

        started = time.monotonic()
        await text_extractor.extract_text(mock_file)

    assert time.monotonic() - started < 1


def pdf_with_pages(*page_texts):
    pages = []
    for page_text in page_texts:
        page = MagicMock()
        page.get_text.return_value = page_text
        pages.append(page)
    mock_doc = MagicMock()
    mock_doc.__enter__.return_value = pages
    return mock_doc


@pytest.mark.asyncio
@pytest.mark.parametrize("pages", [("", ""), ("Page 1 / 2\n", "Page 2 / 2\n")])
async def test_pdf_without_text_stays_empty(text_extractor, pages):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.return_value = b"pdf content"

    with patch("app.services.text_extractor.fitz.open") as mock_fitz_open:
        mock_fitz_open.return_value = pdf_with_pages(*pages)
        text = await text_extractor.extract_text(mock_file)

    assert text == ""


@pytest.mark.asyncio
async def test_page_number_filter_handles_french_spacing_and_keeps_other_lines(
    text_extractor,
):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.return_value = b"pdf content"
    page_text = "Page : 1 / 2\nPage 1 / 3 - suite\n1/2 comprime matin\nPage 2\n"

    with patch("app.services.text_extractor.fitz.open") as mock_fitz_open:
        mock_fitz_open.return_value = pdf_with_pages(page_text)
        text = await text_extractor.extract_text(mock_file)

    assert text == "Page 1 / 3 - suite\n1/2 comprime matin\nPage 2\n"


@pytest.mark.asyncio
async def test_docx_table_cells_merged_across_columns_once_equal_cells_kept(
    text_extractor,
):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = DocxDocument()
    table = document.add_table(rows=1, cols=4)
    table.cell(0, 0).merge(table.cell(0, 1))
    table.cell(0, 0).text = "Prelevement"
    table.cell(0, 2).text = "Negatif"
    table.cell(0, 3).text = "Negatif"
    file_stream = BytesIO()
    document.save(file_stream)
    mock_file.read.return_value = file_stream.getvalue()

    text = await text_extractor.extract_text(mock_file)

    assert "Prelevement : Negatif : Negatif" in text


@pytest.mark.asyncio
async def test_docx_cell_with_several_paragraphs_stays_on_one_line(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = DocxDocument()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Culture"
    table.cell(0, 1).text = "Negative\nen 5 jours"
    file_stream = BytesIO()
    document.save(file_stream)
    mock_file.read.return_value = file_stream.getvalue()

    text = await text_extractor.extract_text(mock_file)

    assert "Culture : Negative en 5 jours" in text


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
async def test_extraction_error_message_carries_no_document_content(text_extractor):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.side_effect = Exception("failed at byte 42: Patient Jean Dupont")

    with pytest.raises(ValueError) as exc_info:
        await text_extractor.extract_text(mock_file)

    assert str(exc_info.value) == "Unable to extract text from the document"


@pytest.mark.asyncio
async def test_extraction_error_is_not_logged_with_document_content(
    text_extractor, caplog
):
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.content_type = "application/pdf"
    mock_file.read.side_effect = Exception("failed at byte 42: Patient Jean Dupont")

    with pytest.raises(ValueError):
        await text_extractor.extract_text(mock_file)

    assert "Jean Dupont" not in caplog.text
    assert "Text extraction failed" in caplog.text
