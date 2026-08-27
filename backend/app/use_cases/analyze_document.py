import logging
from typing import Dict, List, Optional, Tuple

from fastapi import UploadFile

from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.schemas.summary import ClinicalSummary
from app.services.summarizer import summarize

logger = logging.getLogger(__name__)


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
) -> Tuple[ClinicalSummary, List[Optional[Dict[str, List[EntityDetail]]]]]:
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
    :return: The merged summary, and the per-document entities behind it in
        submission order with `None` for each document that could not be read.
    :raises UnreadableDocument: If no submitted document could be read.
    """
    documents: List[Optional[Dict[str, List[EntityDetail]]]] = []
    for file in files:
        try:
            _, entities = await analyze_document(file, text_extractor, entity_extractor)
        except UnreadableDocument:
            # The one operational signal that a document was dropped. A batch
            # that silently returns a shorter summary is how an extraction
            # regression - a PDF text layer that stops being read after an
            # upgrade - would otherwise reach a clinician as a cheerful 200.
            # The position is safe to log; the filename and the text are not.
            logger.warning("Document %d of the batch yielded no text", len(documents))
            documents.append(None)
        else:
            documents.append(entities)

    if not any(entities is not None for entities in documents):
        raise UnreadableDocument()

    return summarize(documents), documents
