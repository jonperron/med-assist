"""Shared input validation helpers for the API boundary."""

from uuid import UUID

from fastapi import HTTPException


def parse_file_id(raw_file_id: str) -> UUID:
    """Validate and convert a file id to UUID without leaking internals."""
    try:
        return UUID(raw_file_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid file ID format. Expected UUID."},
        ) from exc
