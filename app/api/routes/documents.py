"""Document extraction API routes."""

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile, status

from app.core.errors import AppException
from app.core.streaming import read_upload_file_bounded
from app.schemas.document import DocumentExtractResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/extract",
    response_model=DocumentExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text and metadata from a document",
    description=(
        "Accepts a PDF or DOCX document upload via multipart/form-data, "
        "extracts its text, normalizes Unicode content, and returns structured "
        "metadata with word/character counts."
    ),
)
async def extract_document(
    request: Request,
    file: Annotated[
        UploadFile, File(description="A document (PDF or DOCX) to extract.")
    ],
) -> DocumentExtractResponse:
    """Extract and normalize text from an uploaded document."""
    service = DocumentService()

    # 1. Early check via Content-Length header if provided by client
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            declared_bytes = int(content_length_header)
            if declared_bytes > service.settings.max_upload_size_bytes:
                raise AppException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    code="FILE_TOO_LARGE",
                    message=(
                        f"File size ({declared_bytes} bytes) exceeds the maximum "
                        f"allowed limit of {service.settings.max_upload_size_bytes} "
                        "bytes."
                    ),
                )
        except ValueError:
            pass

    # 2. Bounded chunked streaming read to prevent unbounded memory consumption
    try:
        content = await read_upload_file_bounded(
            file=file,
            max_bytes=service.settings.max_upload_size_bytes,
        )
        return await service.process_document_upload(
            filename=file.filename,
            content=content,
        )
    finally:
        await file.close()
