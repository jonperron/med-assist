from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# What the caller is told when a document cannot be read. The same wording on
# every path: the two analysis endpoints answer the same document the same way,
# and neither says anything about what was in it.
UNREADABLE_DOCUMENT = "Unable to extract text from the document."


class ErrorDetail(BaseModel):
    """
    The body of a refusal.

    Routes raise HTTPException with a fixed message, and add context only when
    the context is about the request rather than the document: the allowed file
    types, a size limit, a batch cap. Nothing here quotes document content.
    """

    # The list is closed on purpose. An open body documents nothing, and the
    # next field someone adds next to a parser is the one that carries a
    # filename or a fragment of a document into a response.
    model_config = ConfigDict(extra="forbid")

    message: str = Field(description="Content-free description of the failure")
    allowed_types: Optional[List[str]] = Field(
        default=None, description="File types this endpoint accepts"
    )
    allowed_extensions: Optional[List[str]] = Field(
        default=None, description="File extensions this endpoint accepts"
    )
    received_type: Optional[str] = Field(
        default=None, description="The rejected content type, as the client declared it"
    )
    max_size_bytes: Optional[int] = Field(
        default=None, description="Largest accepted file, in bytes"
    )
    received_size_bytes: Optional[int] = Field(
        default=None, description="Size of the rejected file, in bytes"
    )
    max_files: Optional[int] = Field(
        default=None, description="Largest accepted number of files in one batch"
    )


class ErrorResponse(BaseModel):
    """
    How every refusal reaches the client.

    FastAPI wraps a raised HTTPException as {"detail": ...}, so this is the
    shape the frontend actually parses. Documenting the inner payload alone
    described a body the API never sends.
    """

    detail: ErrorDetail
