"""Unit tests for PDFParser."""

import io

import pytest

from app.core.errors import AppException
from app.parsers.pdf_parser import PDFParser
from tests.pdf_helpers import (
    create_blank_pdf,
    create_corrupted_pdf,
    create_encrypted_pdf,
    create_non_pdf_file,
    create_text_pdf,
)


def test_extract_valid_single_page() -> None:
    """PDFParser extracts page count and text from a single page."""
    pdf_bytes = create_text_pdf(["Hello from PDF"])
    parser = PDFParser()

    page_count, text = parser.extract(io.BytesIO(pdf_bytes))

    assert page_count == 1
    assert "Hello from PDF" in text


def test_extract_valid_multi_page() -> None:
    """PDFParser extracts text across multiple pages."""
    pdf_bytes = create_text_pdf(["Page 1 Content", "Page 2 Content"])
    parser = PDFParser()

    page_count, text = parser.extract(io.BytesIO(pdf_bytes))

    assert page_count == 2
    assert "Page 1 Content" in text
    assert "Page 2 Content" in text


def test_extract_blank_page() -> None:
    """PDFParser returns empty text for a blank page."""
    pdf_bytes = create_blank_pdf(page_count=1)
    parser = PDFParser()

    page_count, text = parser.extract(io.BytesIO(pdf_bytes))

    assert page_count == 1
    assert text == ""


def test_extract_invalid_magic_bytes() -> None:
    """Stream not starting with %PDF- raises UNSUPPORTED_FILE_TYPE (415)."""
    non_pdf = create_non_pdf_file()
    parser = PDFParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(non_pdf))

    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_extract_corrupted_pdf() -> None:
    """Corrupted PDF stream raises INVALID_DOCUMENT (422)."""
    corrupted = create_corrupted_pdf()
    parser = PDFParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(corrupted))

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INVALID_DOCUMENT"


def test_extract_encrypted_pdf() -> None:
    """Password-protected PDF raises ENCRYPTED_DOCUMENT (422)."""
    encrypted = create_encrypted_pdf(password="secret_pass_123")
    parser = PDFParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(encrypted))

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ENCRYPTED_DOCUMENT"
