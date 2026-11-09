"""Unit tests for DOCXParser."""

import io

import pytest

from app.core.errors import AppException
from app.parsers.docx_parser import DOCXParser
from tests.docx_helpers import (
    create_blank_docx,
    create_corrupted_docx,
    create_encrypted_docx,
    create_mixed_docx,
    create_non_docx_file,
    create_text_docx,
    create_zip_without_document_xml,
)


def test_extract_valid_docx_paragraphs() -> None:
    """DOCXParser extracts text from paragraphs with page_count=None."""
    docx_bytes = create_text_docx(["Hello DOCX", "Second Paragraph"])
    parser = DOCXParser()

    page_count, text = parser.extract(io.BytesIO(docx_bytes))

    assert page_count is None
    assert "Hello DOCX" in text
    assert "Second Paragraph" in text


def test_extract_valid_docx_with_table() -> None:
    """DOCXParser extracts table cell text separated by pipes."""
    table_data = [["Col A", "Col B"], ["Val 1", "Val 2"]]
    docx_bytes = create_text_docx(["Table intro"], table_rows=table_data)
    parser = DOCXParser()

    page_count, text = parser.extract(io.BytesIO(docx_bytes))

    assert page_count is None
    assert "Table intro" in text
    assert "Col A | Col B" in text
    assert "Val 1 | Val 2" in text


def test_extract_docx_mixed_natural_order() -> None:
    """DOCXParser preserves natural visual order of paragraphs and tables."""
    elements: list[tuple[str, str | list[list[str]]]] = [
        ("p", "Section 1: Introduction"),
        ("tbl", [["Header 1", "Header 2"], ["Data A", "Data B"]]),
        ("p", "Section 2: Conclusion"),
    ]
    docx_bytes = create_mixed_docx(elements)
    parser = DOCXParser()

    page_count, text = parser.extract(io.BytesIO(docx_bytes))

    assert page_count is None
    intro_idx = text.find("Section 1: Introduction")
    table_idx = text.find("Header 1 | Header 2")
    conclusion_idx = text.find("Section 2: Conclusion")

    assert intro_idx != -1
    assert table_idx != -1
    assert conclusion_idx != -1
    assert intro_idx < table_idx < conclusion_idx


def test_extract_blank_docx() -> None:
    """DOCXParser returns empty string for a document with no text."""
    docx_bytes = create_blank_docx()
    parser = DOCXParser()

    page_count, text = parser.extract(io.BytesIO(docx_bytes))

    assert page_count is None
    assert text == ""


def test_extract_invalid_magic_bytes() -> None:
    """Non-ZIP bytes raise UNSUPPORTED_FILE_TYPE (415)."""
    non_docx = create_non_docx_file()
    parser = DOCXParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(non_docx))

    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_extract_zip_missing_document_xml() -> None:
    """ZIP archive without word/document.xml raises UNSUPPORTED_FILE_TYPE (415)."""
    zip_bytes = create_zip_without_document_xml()
    parser = DOCXParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(zip_bytes))

    assert exc_info.value.status_code == 415
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_extract_corrupted_docx() -> None:
    """Corrupted ZIP archive raises INVALID_DOCUMENT (422)."""
    corrupted = create_corrupted_docx()
    parser = DOCXParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(corrupted))

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INVALID_DOCUMENT"


def test_extract_encrypted_docx() -> None:
    """OLE2 password-protected container raises ENCRYPTED_DOCUMENT (422)."""
    encrypted = create_encrypted_docx()
    parser = DOCXParser()

    with pytest.raises(AppException) as exc_info:
        parser.extract(io.BytesIO(encrypted))

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ENCRYPTED_DOCUMENT"

