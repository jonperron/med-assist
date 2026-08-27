"""The use-case split behind both analysis routes.

`read_documents` and `summarize_read_documents` are what `POST /api/analyze`
and `POST /api/analyze/stream` both go through, so a batch cannot answer the
two endpoints differently. Everything here is exercised through the routes too
(and stays exercised there - this file is not a replacement), but the split
itself deserves tests that do not depend on either HTTP surface: a route test
failing here would say more about serialisation than about the merge itself.
"""

# pylint: disable=W0621
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.use_cases.analyze_document import (
    ReadDocument,
    UnreadableDocument,
    read_documents,
    summarize_documents,
    summarize_read_documents,
)

TEXT = "Le homme de 67 ans a de la fièvre"


def entities():
    return {
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=27, end=33)
        ],
    }


@pytest.fixture
def mock_text_extractor():
    mock = MagicMock(spec=TextExtractionServiceInterface)
    mock.extract_text = AsyncMock(return_value=TEXT)
    return mock


@pytest.fixture
def mock_entity_extractor():
    mock = MagicMock(spec=EntityExtractionServiceInterface)
    mock.extract_entities = AsyncMock(return_value=entities())
    return mock


async def collect(files, text_extractor, entity_extractor):
    return [
        document
        async for document in read_documents(files, text_extractor, entity_extractor)
    ]


class TestReadDocuments:
    """The async generator both routes iterate."""

    @pytest.mark.asyncio
    async def test_yields_one_document_per_file_in_submission_order(
        self, mock_text_extractor, mock_entity_extractor
    ):
        documents = await collect(
            [object(), object(), object()], mock_text_extractor, mock_entity_extractor
        )

        assert len(documents) == 3
        assert all(document.entities == entities() for document in documents)

    @pytest.mark.asyncio
    async def test_an_unreadable_document_keeps_its_place_with_both_halves_none(
        self, mock_text_extractor, mock_entity_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        [document] = await collect(
            [object()], mock_text_extractor, mock_entity_extractor
        )

        assert document == ReadDocument(entities=None, document_date=None)

    @pytest.mark.asyncio
    async def test_a_parser_failure_is_treated_the_same_as_empty_text(
        self, mock_text_extractor, mock_entity_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(
            side_effect=ValueError("could not open the file")
        )

        [document] = await collect(
            [object()], mock_text_extractor, mock_entity_extractor
        )

        assert document.entities is None
        assert document.document_date is None

    @pytest.mark.asyncio
    async def test_the_first_document_being_unreadable_does_not_stop_the_batch(
        self, mock_text_extractor, mock_entity_extractor
    ):
        # The order matters here: a batch that only tolerates a failure at the
        # end would be a narrower guarantee than "the batch carries on".
        mock_text_extractor.extract_text = AsyncMock(side_effect=["", TEXT, TEXT])

        documents = await collect(
            [object(), object(), object()], mock_text_extractor, mock_entity_extractor
        )

        assert [document.entities is not None for document in documents] == [
            False,
            True,
            True,
        ]

    @pytest.mark.asyncio
    async def test_a_document_that_yielded_no_text_is_logged_by_position_only(
        self, mock_text_extractor, mock_entity_extractor, caplog
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        await collect([object()], mock_text_extractor, mock_entity_extractor)

        assert "Document 0 of the batch" in caplog.text
        assert "yielded no text" in caplog.text


class TestSummarizeReadDocuments:
    """Merging documents already read, independent of how they were read."""

    def test_refuses_a_batch_nothing_could_be_read_from(self):
        with pytest.raises(UnreadableDocument):
            summarize_read_documents(
                [
                    ReadDocument(entities=None, document_date=None),
                    ReadDocument(entities=None, document_date=None),
                ]
            )

    def test_summarises_what_could_be_read_around_a_hole_in_the_batch(self):
        summary = summarize_read_documents(
            [
                ReadDocument(entities=None, document_date=None),
                ReadDocument(entities=entities(), document_date=None),
            ]
        )

        assert summary.document_count == 1


class TestSummarizeDocuments:
    """The single-await entry point built from the same two functions."""

    @pytest.mark.asyncio
    async def test_returns_the_summary_and_every_document_in_submission_order(
        self, mock_text_extractor, mock_entity_extractor
    ):
        summary, documents = await summarize_documents(
            files=[object(), object()],
            text_extractor=mock_text_extractor,
            entity_extractor=mock_entity_extractor,
        )

        assert summary.document_count == 2
        assert len(documents) == 2

    @pytest.mark.asyncio
    async def test_raises_when_nothing_in_the_batch_could_be_read(
        self, mock_text_extractor, mock_entity_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        with pytest.raises(UnreadableDocument):
            await summarize_documents(
                files=[object()],
                text_extractor=mock_text_extractor,
                entity_extractor=mock_entity_extractor,
            )
