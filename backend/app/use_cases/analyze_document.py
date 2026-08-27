import logging
from datetime import date
from typing import Dict, List, NamedTuple, Optional, Tuple

from fastapi import UploadFile

from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.schemas.summary import ClinicalSummary
from app.services.document_date import find_document_date
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)


class ReadDocument(NamedTuple):
    """
    One submitted document as the batch left it.

    The two halves travel together because they are read from the same text and
    reported at the same position: the entities the model marked, and the date
    the document carries. Both are `None` for a document that could not be
    read, which keeps its place in the batch either way.
    """

    entities: Optional[Dict[str, List[EntityDetail]]]
    document_date: Optional[date]


class UnreadableDocument(ValueError):
    """
    A document of a supported type that yielded no text.

    A `ValueError` subclass so the routes that answer 400 for it keep doing so,
    and named so a batch can tell it apart from a genuine failure further down:
    one is the caller's document, the other is the server's problem. It carries
    no message about the document - the wording the caller sees is fixed in
    `app.schemas.errors`.
    """


async def analyze_document(
    file: UploadFile,
    text_extractor: TextExtractionServiceInterface,
    entity_extractor: EntityExtractionServiceInterface,
) -> Tuple[str, Dict[str, List[EntityDetail]]]:
    """
    Extract text and entities from one document without storing anything.

    :param file: The uploaded file.
    :param text_extractor: The text extraction service.
    :param entity_extractor: The entity extraction service.
    :return: The document text and its categorised entities.
    :raises UnreadableDocument: If no text could be read from the document.
    """
    try:
        text = await text_extractor.extract_text(file)
    except ValueError as exc:
        # A supported type the parser could not open. Same cause as an empty
        # extraction from the caller's side, so it gets the same answer - and
        # the parser's message, which quotes the bytes that failed, is dropped.
        raise UnreadableDocument() from exc

    if not text:
        raise UnreadableDocument()

    return text, await entity_extractor.extract_entities(text)


async def summarize_documents(
    files: List[UploadFile],
    text_extractor: TextExtractionServiceInterface,
    entity_extractor: EntityExtractionServiceInterface,
) -> Tuple[ClinicalSummary, List[ReadDocument]]:
    """
    Read every submitted document and summarise them as one patient picture.

    The documents are taken to be about the same patient, which is what makes
    merging them meaningful: a finding named in three of them is reported once.
    Nothing is stored, and no document text is returned - the summary is what
    the caller asked for, and the text would only widen what leaves the server.

    A document that cannot be read no longer costs the batch its summary. It is
    kept in place as `None`, the others are summarised, and the caller is told
    which position failed - a summary of three documents out of four, marked as
    such, is worth more to a clinician than a refusal. The whole batch is
    refused only when nothing at all could be read, since there is then no
    summary to degrade to.

    Files are read one after another rather than concurrently: the model admits
    one document at a time by configuration, so gathering them would queue on
    the same semaphore while holding every extracted text in memory at once.

    :param files: The uploaded files.
    :param text_extractor: The text extraction service.
    :param entity_extractor: The entity extraction service.
    :return: The merged summary, and every submitted document in submission
        order - its entities and its date, both `None` where the document could
        not be read.
    :raises UnreadableDocument: If no submitted document could be read.
    """
    documents: List[ReadDocument] = []
    for file in files:
        try:
            text, entities = await analyze_document(
                file, text_extractor, entity_extractor
            )
        except UnreadableDocument:
            # The one operational signal that a document was dropped. A batch
            # that silently returns a shorter summary is how an extraction
            # regression - a PDF text layer that stops being read after an
            # upgrade - would otherwise reach a clinician as a cheerful 200.
            # The position is safe to log; the filename and the text are not.
            logger.warning("Document %d of the batch yielded no text", len(documents))
            documents.append(ReadDocument(entities=None, document_date=None))
        else:
            # The text is dated here and then dropped, as it always was: the
            # date is the only thing about the text itself that the caller
            # asked for, and it leaves nothing behind to return or to store.
            documents.append(
                ReadDocument(entities=entities, document_date=find_document_date(text))
            )

    if not any(document.entities is not None for document in documents):
        raise UnreadableDocument()

    summary = summarize(
        [document.entities for document in documents],
        [document.document_date for document in documents],
    )
    return summary, documents
