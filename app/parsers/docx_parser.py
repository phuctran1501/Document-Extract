"""DOCX document parser implementation using python-docx."""

import zipfile
from typing import BinaryIO

import docx
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.errors import AppException

DOCX_ZIP_MAGIC_BYTES = b"PK\x03\x04"
OLE2_ENCRYPTED_MAGIC_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class DOCXParser:
    """Parser for extracting text and structure from DOCX documents."""

    def extract(self, stream: BinaryIO) -> tuple[None, str]:
        """Extract raw text from a DOCX binary stream.

        Returns:
            tuple[None, str]: (page_count=None, raw_extracted_text)

        Raises:
            AppException: If file is not DOCX (415), corrupted (422),
                         or encrypted (422).
        """
        # 1. Validate magic bytes header
        stream.seek(0)
        header = stream.read(8)

        # Check for OLE2 encryption container used by password-protected Office files
        if header == OLE2_ENCRYPTED_MAGIC_BYTES:
            raise AppException(
                status_code=422,
                code="ENCRYPTED_DOCUMENT",
                message="The DOCX document is password-protected and cannot be read.",
            )

        if not header.startswith(DOCX_ZIP_MAGIC_BYTES):
            raise AppException(
                status_code=415,
                code="UNSUPPORTED_FILE_TYPE",
                message="File content does not match DOCX format.",
            )

        stream.seek(0)

        # 2. Inspect ZIP structure for standard Word document entry
        try:
            with zipfile.ZipFile(stream) as zf:
                namelist = zf.namelist()
                if "word/document.xml" not in namelist:
                    raise AppException(
                        status_code=415,
                        code="UNSUPPORTED_FILE_TYPE",
                        message=(
                            "File is a ZIP archive but does not contain a valid "
                            "DOCX document structure."
                        ),
                    )
        except zipfile.BadZipFile as exc:
            raise AppException(
                status_code=422,
                code="INVALID_DOCUMENT",
                message="The DOCX file is corrupted or could not be parsed.",
            ) from exc

        stream.seek(0)

        # 3. Read document using python-docx
        try:
            doc = docx.Document(stream)
        except (PackageNotFoundError, Exception) as exc:
            raise AppException(
                status_code=422,
                code="INVALID_DOCUMENT",
                message="The DOCX file is corrupted or could not be parsed.",
            ) from exc

        # 4. Extract paragraphs and tables in natural document flow
        blocks: list[str] = []
        try:
            for child in doc.element.body:
                tag = child.tag
                if tag.endswith("p"):
                    p = Paragraph(child, doc)
                    text = p.text.strip()
                    if text:
                        blocks.append(text)
                elif tag.endswith("tbl"):
                    table = Table(child, doc)
                    for row in table.rows:
                        row_cells = [
                            cell.text.strip() for cell in row.cells if cell.text.strip()
                        ]
                        if row_cells:
                            blocks.append(" | ".join(row_cells))
        except Exception as exc:
            raise AppException(
                status_code=422,
                code="INVALID_DOCUMENT",
                message="Failed to read body content from DOCX document.",
            ) from exc

        raw_text = "\n\n".join(blocks)
        return None, raw_text
