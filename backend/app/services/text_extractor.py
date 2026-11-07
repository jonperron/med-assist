import logging
import re
from io import BytesIO
from typing import Optional
import fitz
from docx import Document
from fastapi import UploadFile

from app.interfaces.service_interfaces import TextExtractionServiceInterface

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PLAINTEXT_CONTENT_TYPE = "text/plain"
SUPPORTED_CONTENT_TYPES = frozenset(
    {PDF_CONTENT_TYPE, DOCX_CONTENT_TYPE, PLAINTEXT_CONTENT_TYPE}
)

# "Page : 1 / 1", "Page 1 sur 3": pure layout, never clinical content.
PAGE_NUMBER_LINE = re.compile(
    r"^[ \t]*Page[ \t]*:?[ \t]*\d+[ \t]*(?:/|sur)[ \t]*\d+[ \t]*$\n?",
    re.IGNORECASE | re.MULTILINE,
)


class TextExtractor(TextExtractionServiceInterface):
    async def extract_text(self, file: UploadFile) -> Optional[str]:
        """
        Extracts text from the document based on its file type.
        """
        if file.content_type not in SUPPORTED_CONTENT_TYPES:
            raise ValueError("Unsupported file type")

        try:
            file_bytes = BytesIO(await file.read())

            if file.content_type == PDF_CONTENT_TYPE:
                return self.extract_text_from_pdf(file_bytes)

            if file.content_type == DOCX_CONTENT_TYPE:
                return self.extract_text_from_docx(file_bytes)

            return self.extract_text_from_plaintext(file_bytes)
        except Exception as e:
            # Parser errors routinely quote the bytes that failed to parse, so
            # neither the message nor a traceback may reach the log or the caller.
            logger.error(
                "Text extraction failed for a %s document (%s)",
                file.content_type,
                type(e).__name__,
            )
            raise ValueError("Unable to extract text from the document") from e

    def extract_text_from_pdf(self, file_bytes: BytesIO) -> str:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            pages = [PAGE_NUMBER_LINE.sub("", page.get_text()) for page in doc]
        # A newline between pages keeps the last line of one page from fusing
        # with the first line of the next into a single entity.
        return "\n".join(pages)

    def extract_text_from_docx(self, file_bytes: BytesIO) -> str:
        doc = Document(file_bytes)
        lines = [paragraph.text for paragraph in doc.paragraphs]
        # shortcut: tables follow the paragraphs instead of sitting in body
        # order; upgrade if reading order starts to matter for a layout.
        for table in doc.tables:
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    # python-docx repeats a merged cell once per column it spans.
                    if cell.text and (not cells or cells[-1] != cell.text):
                        cells.append(cell.text)
                if cells:
                    lines.append(" : ".join(cells))
        return "\n".join(lines)

    def extract_text_from_plaintext(self, file_bytes: BytesIO) -> str:
        return file_bytes.getvalue().decode("utf-8")
