import pytest
from fastapi import HTTPException
from io import BytesIO

from app.use_cases.validate_file import validate_upload_file


class DummyUploadFile:
    def __init__(self, filename, content_type):
        self.filename = filename
        self.content_type = content_type
        self.file = BytesIO(b"dummy content")

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


@pytest.mark.asyncio
async def test_validate_upload_file_invalid_extension():
    file = DummyUploadFile("document.exe", "application/pdf")
    with pytest.raises(HTTPException) as exc:
        await validate_upload_file(file)
    assert exc.value.status_code == 400
    assert "Invalid file extension" in exc.value.detail["message"]
