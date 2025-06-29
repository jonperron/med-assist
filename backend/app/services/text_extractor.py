
from io import BytesIO
import fitz
from docx import Document
from fastapi import UploadFile

class TextExtractor:

    async def extract_text(self, file: UploadFile) -> str:
        """
        Extracts text from the document based on its file type.
        """
        try:
            contents = await file.read()
            file_bytes = BytesIO(contents)

            if file.content_type == 'application/pdf':
                return self._extract_text_from_pdf(file_bytes)
            elif file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                return self._extract_text_from_docx(file_bytes)
            elif file.content_type == "text/plain":
                return self._extract_text_from_plaintext(file_bytes)
            else:
                raise ValueError("Unsupported file type")
        except Exception as e:
            raise ValueError(f"Error extracting text: {str(e)}")
    

    def _extract_text_from_pdf(self, file_bytes: BytesIO) -> str:
        text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text

    def _extract_text_from_docx(self, file_bytes: BytesIO) -> str:
        doc = Document(file_bytes)
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)

    def _extract_text_from_plaintext(self, file_bytes: BytesIO) -> str:
        return file_bytes.getvalue().decode('utf-8')
