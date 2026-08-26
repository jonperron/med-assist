from typing import Dict, List, Tuple

from fastapi import UploadFile

from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.schemas.summary import ClinicalSummary
from app.services.summarizer import summarize


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
    :raises ValueError: If no text could be extracted from the document.
    """
    text = await text_extractor.extract_text(file)
    if not text:
        raise ValueError("The document contains no extractable text")

    return text, await entity_extractor.extract_entities(text)


async def summarize_documents(
    files: List[UploadFile],
    text_extractor: TextExtractionServiceInterface,
    entity_extractor: EntityExtractionServiceInterface,
) -> Tuple[ClinicalSummary, List[Dict[str, List[EntityDetail]]]]:
    """
    Read every submitted document and summarise them as one patient picture.

    The documents are taken to be about the same patient, which is what makes
    merging them meaningful: a finding named in three of them is reported once.
    Nothing is stored, and no document text is returned - the summary is what
    the caller asked for, and the text would only widen what leaves the server.

    Files are read one after another rather than concurrently: the model admits
    one document at a time by configuration, so gathering them would queue on
    the same semaphore while holding every extracted text in memory at once.

    :param files: The uploaded files.
    :param text_extractor: The text extraction service.
    :param entity_extractor: The entity extraction service.
    :return: The merged summary and the per-document entities behind it.
    :raises ValueError: If a document yields no extractable text.
    """
    documents = []
    for file in files:
        _, entities = await analyze_document(file, text_extractor, entity_extractor)
        documents.append(entities)

    return summarize(documents), documents
