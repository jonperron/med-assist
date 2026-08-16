import pytest
from fastapi import HTTPException
from io import BytesIO

from app.schemas.errors import ErrorDetail
from app.use_cases.validate_file import validate_upload_file


def assert_body_is_documented(detail):
    """Every refusal body must be one the published schema describes.

    ErrorDetail forbids unknown keys, so a field added next to a parser - the
    kind that ends up holding a filename or a fragment of a document - fails
    here rather than reaching a client.
    """
    ErrorDetail(**detail)


class DummyUploadFile:
    def __init__(self, filename, content_type, content: bytes = b"dummy content"):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(content)

    async def read(self):
        return self.file.getvalue()

    async def seek(self, pos):
        self.file.seek(pos)


@pytest.mark.asyncio
async def test_validate_upload_file_valid():
    file = DummyUploadFile("document.pdf", "application/pdf")
    assert await validate_upload_file(file) is True


@pytest.mark.asyncio
async def test_validate_upload_file_invalid_content_type():
    file = DummyUploadFile("document.pdf", "application/zip")
    with pytest.raises(HTTPException) as exc:
        await validate_upload_file(file)
    assert exc.value.status_code == 400
    assert "Invalid file type" in exc.value.detail["message"]
    assert_body_is_documented(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_upload_file_rejects_doc_content_type():
    file = DummyUploadFile("document.doc", "application/msword")
    with pytest.raises(HTTPException) as exc:
        await validate_upload_file(file)
    assert exc.value.status_code == 400
    assert "Invalid file type" in exc.value.detail["message"]
    assert_body_is_documented(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_upload_file_invalid_extension():
    file = DummyUploadFile("document.exe", "application/pdf")
    with pytest.raises(HTTPException) as exc:
        await validate_upload_file(file)
    assert exc.value.status_code == 400
    assert "Invalid file extension" in exc.value.detail["message"]
    assert_body_is_documented(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_upload_file_too_large():
    oversized_content = b"a" * (10 * 1024 * 1024 + 1)
    file = DummyUploadFile("document.pdf", "application/pdf", oversized_content)
    with pytest.raises(HTTPException) as exc:
        await validate_upload_file(file)
    assert exc.value.status_code == 413
    assert "File too large" in exc.value.detail["message"]
    assert_body_is_documented(exc.value.detail)
