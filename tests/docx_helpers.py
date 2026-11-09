"""Helper functions to generate in-memory DOCX files for testing."""

import io
import zipfile

import docx


def create_text_docx(
    paragraphs: list[str],
    table_rows: list[list[str]] | None = None,
) -> bytes:
    """Create an in-memory DOCX containing paragraphs and an optional table."""
    doc = docx.Document()

    for p_text in paragraphs:
        doc.add_paragraph(p_text)

    if table_rows and len(table_rows) > 0:
        col_count = max(len(row) for row in table_rows)
        table = doc.add_table(rows=len(table_rows), cols=col_count)
        for r_idx, row_data in enumerate(table_rows):
            for c_idx, cell_value in enumerate(row_data):
                table.cell(r_idx, c_idx).text = cell_value

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_mixed_docx(
    elements: list[tuple[str, str | list[list[str]]]],
) -> bytes:
    """Create an in-memory DOCX with ordered paragraphs and tables.

    `elements` is a list of tuples:
    - ("p", "Paragraph text")
    - ("tbl", [["Row1 Col1", "Row1 Col2"], ["Row2 Col1", "Row2 Col2"]])
    """
    doc = docx.Document()

    for elem_type, elem_val in elements:
        if elem_type == "p":
            assert isinstance(elem_val, str)
            doc.add_paragraph(elem_val)
        elif elem_type == "tbl":
            assert isinstance(elem_val, list)
            if len(elem_val) > 0:
                col_count = max(len(row) for row in elem_val)
                table = doc.add_table(rows=len(elem_val), cols=col_count)
                for r_idx, row_data in enumerate(elem_val):
                    for c_idx, cell_value in enumerate(row_data):
                        table.cell(r_idx, c_idx).text = cell_value

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_blank_docx() -> bytes:
    """Create an in-memory DOCX with no text content."""
    doc = docx.Document()
    doc.add_paragraph("")  # Empty paragraph

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_corrupted_docx() -> bytes:
    """Create a byte sequence that starts with PK\\x03\\x04 but has broken ZIP data."""
    return b"PK\x03\x04\nCorrupted DOCX archive with broken central directory"


def create_encrypted_docx() -> bytes:
    """Create an in-memory OLE2 header (used by encrypted Office files)."""
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 128


def create_zip_without_document_xml() -> bytes:
    """Create a valid ZIP file that is missing word/document.xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notes.txt", "This is just a text file in a zip.")
    return buf.getvalue()


def create_non_docx_file() -> bytes:
    """Create plain non-ZIP bytes."""
    return b"This is plain text, not a DOCX document."
