"""Helper functions to generate in-memory PDFs for testing."""

import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def create_text_pdf(texts: list[str]) -> bytes:
    """Create an in-memory PDF with specified text on each page."""
    writer = PdfWriter()

    for text in texts:
        page = writer.add_blank_page(width=300, height=300)

        # Stream with text operators
        content_stream = DecodedStreamObject()
        content_bytes = f"BT /F1 12 Tf 50 200 Td ({text}) Tj ET".encode("latin-1")
        content_stream.set_data(content_bytes)
        page[NameObject("/Contents")] = content_stream

        # Font resource
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font,
                    }
                )
            }
        )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_blank_pdf(page_count: int = 1) -> bytes:
    """Create an in-memory PDF with blank pages (no extractable text)."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_encrypted_pdf(password: str = "secret123") -> bytes:
    """Create an in-memory password-protected PDF."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(password)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def create_corrupted_pdf() -> bytes:
    """Create a byte sequence that starts with %PDF- but has corrupted body."""
    return b"%PDF-1.7\nCorrupted byte stream with invalid xref and objects"


def create_non_pdf_file() -> bytes:
    """Create a plain text or non-PDF binary byte sequence."""
    return b"This is a plain text file, not a PDF document."
