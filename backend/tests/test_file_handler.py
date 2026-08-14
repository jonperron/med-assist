# pylint: disable=W0621
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile

from app.core.config import PrivacyConfiguration
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.interfaces.service_interfaces import EntityExtractionServiceInterface
from app.schemas.extraction import EntityDetail
from app.services.file_handler import FileHandler
from app.services.pseudonymizer import Pseudonymizer


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
    mock.save_entities = AsyncMock()
    mock.save_batch = AsyncMock()
    return mock


@pytest.fixture
def extracted_entities():
    return {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=3, end=8)
        ],
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=12, end=18)
        ],
    }


@pytest.fixture
def mock_entity_extractor(extracted_entities):
    mock = MagicMock(spec=EntityExtractionServiceInterface)
    mock.extract_entities.return_value = extracted_entities
    return mock


def build_handler(
    text_repository,
    entity_extractor,
    store_document_text=False,
    pseudonymize=False,
):
    return FileHandler(
        text_repository=text_repository,
        entity_extractor=entity_extractor,
        privacy_config=PrivacyConfiguration(
            STORE_DOCUMENT_TEXT=store_document_text,
            PSEUDONYMIZE_ENTITIES=pseudonymize,
        ),
        pseudonymizer=Pseudonymizer(),
    )


@patch("app.services.file_handler.TextExtractor")
def test_file_handler_init(
    MockTextExtractor, mock_text_repository, mock_entity_extractor
):
    handler = build_handler(mock_text_repository, mock_entity_extractor)
    MockTextExtractor.assert_called_once()
    assert handler.extractor is not None
    assert handler.text_repository is not None


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_stores_entities_not_text(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(
        return_value="Le homme a fièvre"
    )
    handler = build_handler(mock_text_repository, mock_entity_extractor)
    file_id = uuid4()

    result = await handler.process_file(file_id, mock_upload_file)

    assert result is True
    mock_entity_extractor.extract_entities.assert_called_once_with("Le homme a fièvre")
    mock_text_repository.save_text.assert_not_called()
    mock_text_repository.save_entities.assert_called_once()
    stored_id, stored_entities = mock_text_repository.save_entities.call_args.args
    assert stored_id == file_id
    assert stored_entities["symptoms"][0].text == "fièvre"


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_drops_offsets_when_text_is_not_kept(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(
        return_value="Le homme a fièvre"
    )
    handler = build_handler(mock_text_repository, mock_entity_extractor)

    await handler.process_file(uuid4(), mock_upload_file)

    _, stored_entities = mock_text_repository.save_entities.call_args.args
    for details in stored_entities.values():
        for entity in details:
            assert entity.start is None
            assert entity.end is None


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_keeps_text_and_offsets_when_configured(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(
        return_value="Le homme a fièvre"
    )
    handler = build_handler(
        mock_text_repository, mock_entity_extractor, store_document_text=True
    )
    file_id = uuid4()

    await handler.process_file(file_id, mock_upload_file)

    mock_text_repository.save_text.assert_called_once_with(file_id, "Le homme a fièvre")
    _, stored_entities = mock_text_repository.save_entities.call_args.args
    assert stored_entities["symptoms"][0].start == 12


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_pseudonymizes_when_configured(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(
        return_value="Le homme a fièvre"
    )
    handler = build_handler(
        mock_text_repository,
        mock_entity_extractor,
        store_document_text=True,
        pseudonymize=True,
    )

    await handler.process_file(uuid4(), mock_upload_file)

    _, stored_text = mock_text_repository.save_text.call_args.args
    assert "homme" not in stored_text
    assert "[GENRE_1]" in stored_text


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_request_overrides_the_configured_default(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(
        return_value="Le homme a fièvre"
    )
    handler = build_handler(
        mock_text_repository, mock_entity_extractor, store_document_text=True
    )

    await handler.process_file(uuid4(), mock_upload_file, pseudonymize=True)

    _, stored_text = mock_text_repository.save_text.call_args.args
    assert "homme" not in stored_text


@pytest.mark.asyncio
@patch("app.services.file_handler.TextExtractor")
async def test_process_file_no_text(
    MockTextExtractor, mock_text_repository, mock_entity_extractor, mock_upload_file
):
    MockTextExtractor.return_value.extract_text = AsyncMock(return_value=None)
    handler = build_handler(mock_text_repository, mock_entity_extractor)

    result = await handler.process_file(uuid4(), mock_upload_file)

    assert result is False
    mock_entity_extractor.extract_entities.assert_not_called()
    mock_text_repository.save_text.assert_not_called()
    mock_text_repository.save_entities.assert_not_called()


@pytest.mark.asyncio
async def test_file_handler_process_batch_success(
    mock_text_repository, mock_entity_extractor
):
    batch_id = uuid4()
    file_ids = ["file1", "file2", "file3"]

    handler = build_handler(mock_text_repository, mock_entity_extractor)
    result = await handler.process_batch(batch_id, file_ids)
    mock_text_repository.save_batch.assert_called_once_with(batch_id, file_ids)
    assert result is True


@pytest.mark.asyncio
async def test_file_handler_process_batch_failure(
    mock_text_repository, mock_entity_extractor
):
    mock_text_repository.save_batch = AsyncMock(side_effect=Exception("Save failed"))

    handler = build_handler(mock_text_repository, mock_entity_extractor)

    with pytest.raises(Exception):
        await handler.process_batch(uuid4(), ["file1", "file2"])
