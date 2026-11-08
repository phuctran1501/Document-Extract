"""Pydantic schemas for document extraction API."""

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata about the processed document."""

    filename: str = Field(
        ..., description="Original filename of the uploaded document."
    )
    media_type: str = Field(..., description="Detected media type of the file.")
    size_bytes: int = Field(..., ge=0, description="Total size in bytes.")
    format: str = Field(..., description="Normalized document format (e.g. pdf, docx).")


class ExtractionResult(BaseModel):
    """Extracted text and statistical counters."""

    text: str = Field(..., description="Normalized document text.")
    page_count: int | None = Field(
        default=None,
        ge=0,
        description="Page count (null for unpaged formats like DOCX).",
    )
    character_count: int = Field(
        ..., ge=0, description="Total characters in normalized text."
    )
    word_count: int = Field(..., ge=0, description="Total words in normalized text.")


class DocumentExtractResponse(BaseModel):
    """Standard response model for POST /api/v1/documents/extract."""

    document: DocumentMetadata
    extraction: ExtractionResult
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during extraction.",
    )
