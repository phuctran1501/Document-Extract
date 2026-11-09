"""Document processing orchestration service."""

import io

from app.core.config import get_settings
from app.core.errors import AppException
from app.parsers.docx_parser import DOCXParser
from app.parsers.pdf_parser import PDFParser
from app.schemas.document import (
    DocumentExtractResponse,
    DocumentMetadata,
    ExtractionResult,
)
from app.services.text_service import analyze_text


class DocumentService:
    """Service coordinating document validation, parsing, and text normalization."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.pdf_parser = PDFParser()
        self.docx_parser = DOCXParser()

    async def process_document_upload(
        self,
        filename: str | None,
        content: bytes,
    ) -> DocumentExtractResponse:
        """Validate, parse, normalize, and extract text and metadata from upload.

        Args:
            filename: The name provided by the client (sanitized to basename only).
            content: Raw file bytes.

        Returns:
            DocumentExtractResponse: Structured extraction result and metadata.

        Raises:
            AppException: For empty files (400), oversized files (413),
                         unsupported types (415), corrupted/encrypted files (422),
                         or no extractable text (422).
        """
        # 1. Clean filename
        safe_filename = filename.strip() if filename else "unnamed_document"
        # Extract only the base name (security: no path traversal)
        safe_filename = safe_filename.replace("\\", "/").split("/")[-1]

        # 2. Validate empty payload
        file_size = len(content)
        if file_size == 0:
            raise AppException(
                status_code=400,
                code="INVALID_REQUEST",
                message="Uploaded file is empty (0 bytes).",
            )

        # 3. Validate size limit
        max_bytes = self.settings.max_upload_size_bytes
        if file_size > max_bytes:
            raise AppException(
                status_code=413,
                code="FILE_TOO_LARGE",
                message=(
                    f"File size ({file_size} bytes) exceeds the maximum allowed "
                    f"limit of {max_bytes} bytes."
                ),
            )

        # 4. Determine format from filename
        lower_name = safe_filename.lower()
        if lower_name.endswith(".pdf"):
            doc_format = "pdf"
            media_type = "application/pdf"
        elif lower_name.endswith(".docx"):
            doc_format = "docx"
            media_type = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        else:
            raise AppException(
                status_code=415,
                code="UNSUPPORTED_FILE_TYPE",
                message="Only PDF and DOCX files are supported.",
            )

        # 5. Parse document
        stream = io.BytesIO(content)
        if doc_format == "pdf":
            page_count, raw_text = self.pdf_parser.extract(stream)
        else:
            page_count, raw_text = self.docx_parser.extract(stream)

        # 6. Normalize extracted text & calculate deterministic statistics
        normalized_text, stats = analyze_text(raw_text)

        # 7. Check for extractable text (no OCR fallback per NFR-01 / FR-09)
        if stats.character_count == 0:
            raise AppException(
                status_code=422,
                code="NO_EXTRACTABLE_TEXT",
                message=(
                    f"The {doc_format.upper()} document contains no extractable text. "
                    "Scanned documents requiring OCR are not supported."
                ),
            )

        # 8. Build response model
        return DocumentExtractResponse(
            document=DocumentMetadata(
                filename=safe_filename,
                media_type=media_type,
                size_bytes=file_size,
                format=doc_format,
            ),
            extraction=ExtractionResult(
                text=normalized_text,
                page_count=page_count,
                character_count=stats.character_count,
                word_count=stats.word_count,
            ),
            warnings=[],
        )
