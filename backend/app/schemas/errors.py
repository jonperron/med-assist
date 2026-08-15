from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """
    The body of a refusal.

    Routes raise HTTPException with a fixed message, and add context only when
    the context is about the request rather than the document: the allowed file
    types, a size limit, a batch cap. Nothing here quotes document content.
    """

    # Individual routes add request-level context alongside the message.
    model_config = ConfigDict(extra="allow")

    message: str = Field(description="Content-free description of the failure")


class ErrorResponse(BaseModel):
    """
    How every refusal reaches the client.

    FastAPI wraps a raised HTTPException as {"detail": ...}, so this is the
    shape the frontend actually parses. Documenting the inner payload alone
    described a body the API never sends.
    """

    detail: ErrorDetail
