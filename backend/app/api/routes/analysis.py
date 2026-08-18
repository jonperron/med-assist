import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.dependencies import (
    get_entity_extractor,
    get_privacy_config,
    get_pseudonymizer,
    get_text_extractor,
)
from app.core.config import PrivacyConfiguration
from app.core.readiness import require_the_model
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.errors import UNREADABLE_DOCUMENT, ErrorResponse
from app.schemas.extraction import AnalysisResponse, ExtractedEntities
from app.services.pseudonymizer import Pseudonymizer
from app.use_cases.analyze_document import analyze_document
from app.use_cases.validate_file import validate_upload_file

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_the_model)],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or unreadable document"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
    },
)
async def analyze(
    file: UploadFile = File(..., description="The file to analyze (PDF, DOCX, TXT)."),
    pseudonymize: bool | None = Form(
        default=None,
        description=(
            "Mask entities detected as patient information. Defaults to the "
            "deployment's PSEUDONYMIZE_ENTITIES setting."
        ),
    ),
    text_extractor: TextExtractionServiceInterface = Depends(get_text_extractor),
    entity_extractor: EntityExtractionServiceInterface = Depends(get_entity_extractor),
    pseudonymizer: Pseudonymizer = Depends(get_pseudonymizer),
    privacy_config: PrivacyConfiguration = Depends(get_privacy_config),
) -> AnalysisResponse:
    """
    Analyze a medical document in a single request, storing nothing.

    The document is read, analysed and answered in memory. No file id is issued
    because there is nothing to come back for, and nothing to delete later.

    Args:
        file: The uploaded file (PDF, DOCX, TXT)
        pseudonymize: Whether to mask detected patient identifiers

    Returns:
        AnalysisResponse: The extracted text and its medical entities

    Raises:
        HTTPException: 400 for an invalid or unreadable file, 500 for server errors
    """
    await validate_upload_file(file)

    # A request may ask for masking, never turn a deployment's policy off.
    should_mask = privacy_config.pseudonymize or bool(pseudonymize)

    try:
        text, entities = await analyze_document(
            file=file,
            text_extractor=text_extractor,
            entity_extractor=entity_extractor,
            pseudonymizer=pseudonymizer,
            pseudonymize=should_mask,
        )
        # Built inside the guard: a schema mismatch raises a pydantic error that
        # quotes the offending value, which would be document content.
        return AnalysisResponse(
            text=text,
            extracted_entities=ExtractedEntities(**entities),
            mapping_info=entity_extractor.get_mapping_info(),
            pseudonymized=should_mask,
        )
    except ValidationError as exc:
        # A pydantic error quotes the value it rejected, so it is never
        # forwarded: ValidationError subclasses ValueError, hence the ordering.
        logger.error("Analysis produced an unexpected entity shape")
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from exc
    except ValueError as exc:
        # Raised for an unreadable document. The message is fixed upstream and
        # carries no document content.
        raise HTTPException(
            status_code=400,
            detail={"message": UNREADABLE_DOCUMENT},
        ) from exc
    except Exception as exc:
        logger.error("Analysis failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from exc
