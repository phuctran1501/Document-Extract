"""PDF document parser implementation using pypdf."""

from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import AppException

PDF_MAGIC_BYTES = b"%PDF-"


class PDFParser:
    """Parser for extracting text and metadata from PDF files."""

    def extract(self, stream: BinaryIO) -> tuple[int, str]:
        """Extract page count and raw text from a PDF binary stream.

        Returns:
            tuple[int, str]: (page_count, raw_extracted_text)

        Raises:
            AppException: If file is not a PDF (415), corrupted (422),
                         or encrypted (422).
        """
        # 1. Validate magic bytes header
        stream.seek(0)
        header = stream.read(5)
        if header != PDF_MAGIC_BYTES:
            raise AppException(
                status_code=415,
                code="UNSUPPORTED_FILE_TYPE",
                message="File content does not match PDF format.",
            )

        stream.seek(0)

        # 2. Read PDF structure with pypdf
        try:
            reader = PdfReader(stream)
        except (PdfReadError, Exception) as exc:
            raise AppException(
                status_code=422,
                code="INVALID_DOCUMENT",
                message="The PDF file is corrupted or could not be parsed.",
            ) from exc

        # 3. Check for password encryption
        if reader.is_encrypted:
            try:
                # Attempt empty password decryption
                decrypt_result = reader.decrypt("")
                if decrypt_result == 0:
                    raise AppException(
                        status_code=422,
                        code="ENCRYPTED_DOCUMENT",
                        message=(
                            "The PDF document is password-protected and cannot be read."
                        ),
                    )
            except Exception as exc:
                if isinstance(exc, AppException):
                    raise
                raise AppException(
                    status_code=422,
                    code="ENCRYPTED_DOCUMENT",
                    message=(
                        "The PDF document is password-protected and cannot be read."
                    ),
                ) from exc

        # 4. Extract text page by page
        page_texts: list[str] = []
        try:
            page_count = len(reader.pages)
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    page_texts.append(text)
        except Exception as exc:
            raise AppException(
                status_code=422,
                code="INVALID_DOCUMENT",
                message="Failed to read pages from PDF document.",
            ) from exc

        raw_text = "\n\n".join(page_texts)
        return page_count, raw_text
