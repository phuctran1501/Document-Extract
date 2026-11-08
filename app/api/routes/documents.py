"""Document extraction API routes."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.schemas.document import DocumentExtractResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/extract",
    response_model=DocumentExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text and metadata from a document",
    description=(
        "Accepts a PDF document upload via multipart/form-data, extracts its text, "
        "normalizes Unicode content, and returns structured metadata with "
        "word/character counts."
    ),
)
async def extract_document(
    file: Annotated[UploadFile, File(description="A PDF document to extract.")],
) -> DocumentExtractResponse:
    """Extract and normalize text from an uploaded document."""
    service = DocumentService()
    try:
        content = await file.read()
        return await service.process_document_upload(
            filename=file.filename,
            content=content,
        )
    finally:
        await file.close()
