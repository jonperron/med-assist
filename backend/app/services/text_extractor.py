import logging
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
                return self._extract_text_from_pdf(file_bytes)

            if file.content_type == DOCX_CONTENT_TYPE:
                return self._extract_text_from_docx(file_bytes)

            return self._extract_text_from_plaintext(file_bytes)
        except Exception as e:
            # Parser errors routinely quote the bytes that failed to parse, so
            # neither the message nor a traceback may reach the log or the caller.
            logger.error(
                "Text extraction failed for a %s document (%s)",
                file.content_type,
                type(e).__name__,
            )
            raise ValueError("Unable to extract text from the document") from e

    def _extract_text_from_pdf(self, file_bytes: BytesIO) -> str:
        text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text

    def _extract_text_from_docx(self, file_bytes: BytesIO) -> str:
        doc = Document(file_bytes)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)

    def _extract_text_from_plaintext(self, file_bytes: BytesIO) -> str:
        return file_bytes.getvalue().decode("utf-8")
