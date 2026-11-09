"""Integration tests for POST /api/v1/documents/extract."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.correlation import CORRELATION_ID_HEADER
from tests.docx_helpers import (
    create_blank_docx,
    create_corrupted_docx,
    create_encrypted_docx,
    create_text_docx,
    create_zip_without_document_xml,
)
from tests.pdf_helpers import (
    create_blank_pdf,
    create_corrupted_pdf,
    create_encrypted_pdf,
    create_non_pdf_file,
    create_text_pdf,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ==============================================================================
# PDF Extraction Tests
# ==============================================================================


def test_extract_pdf_success(client: TestClient) -> None:
    """Valid PDF returns HTTP 200 with structured metadata and text."""
    pdf_bytes = create_text_pdf(["Software Engineer Resume Content"])
    files = {"file": ("resume.pdf", pdf_bytes, "application/pdf")}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 200
    data = response.json()

    assert "document" in data
    assert "extraction" in data
    assert "warnings" in data

    doc = data["document"]
    assert doc["filename"] == "resume.pdf"
    assert doc["media_type"] == "application/pdf"
    assert doc["format"] == "pdf"
    assert doc["size_bytes"] == len(pdf_bytes)

    ext = data["extraction"]
    assert "Software Engineer Resume Content" in ext["text"]
    assert ext["page_count"] == 1
    assert ext["character_count"] > 0
    assert ext["word_count"] == 4

    assert CORRELATION_ID_HEADER in response.headers


def test_extract_empty_file_returns_400(client: TestClient) -> None:
    """Uploading a 0-byte file returns HTTP 400 with INVALID_REQUEST."""
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_extract_unsupported_extension_returns_415(client: TestClient) -> None:
    """Uploading an unsupported extension returns HTTP 415."""
    files = {"file": ("image.png", b"fake-png-bytes", "image/png")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_extract_fake_pdf_magic_bytes_mismatch_returns_415(
    client: TestClient,
) -> None:
    """A file named .pdf but without %PDF- magic bytes returns HTTP 415."""
    non_pdf = create_non_pdf_file()
    files = {"file": ("fake.pdf", non_pdf, "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_extract_corrupted_pdf_returns_422(client: TestClient) -> None:
    """A corrupted PDF stream returns HTTP 422 with INVALID_DOCUMENT."""
    corrupted = create_corrupted_pdf()
    files = {"file": ("broken.pdf", corrupted, "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_DOCUMENT"


def test_extract_encrypted_pdf_returns_422(client: TestClient) -> None:
    """A password-protected PDF returns HTTP 422 with ENCRYPTED_DOCUMENT."""
    encrypted = create_encrypted_pdf(password="secret_pass_999")
    files = {"file": ("protected.pdf", encrypted, "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "ENCRYPTED_DOCUMENT"


def test_extract_scanned_pdf_no_text_returns_422(client: TestClient) -> None:
    """A blank PDF with no extractable text returns HTTP 422 NO_EXTRACTABLE_TEXT."""
    blank = create_blank_pdf(page_count=2)
    files = {"file": ("scanned.pdf", blank, "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "NO_EXTRACTABLE_TEXT"


def test_extract_preserves_correlation_id(client: TestClient) -> None:
    """The incoming X-Correlation-ID is preserved in the response."""
    client_id = "test-extract-corr-456"
    pdf_bytes = create_text_pdf(["Testing Correlation Header"])
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}

    response = client.post(
        "/api/v1/documents/extract",
        files=files,
        headers={CORRELATION_ID_HEADER: client_id},
    )

    assert response.status_code == 200
    assert response.headers.get(CORRELATION_ID_HEADER) == client_id


def test_extract_file_too_large_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files exceeding max_upload_size_bytes return HTTP 413 FILE_TOO_LARGE."""
    small_settings = Settings(max_upload_size_bytes=50)
    monkeypatch.setattr(
        "app.services.document_service.get_settings", lambda: small_settings
    )

    pdf_bytes = create_text_pdf(["Sample content exceeding 50 bytes"])
    files = {"file": ("large.pdf", pdf_bytes, "application/pdf")}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "FILE_TOO_LARGE"


# ==============================================================================
# DOCX Extraction Tests
# ==============================================================================


def test_extract_docx_success(client: TestClient) -> None:
    """Valid DOCX returns HTTP 200, format='docx', page_count=None."""
    docx_bytes = create_text_docx(["Project Overview", "Technical Architecture"])
    files = {"file": ("specification.docx", docx_bytes, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 200
    data = response.json()

    doc = data["document"]
    assert doc["filename"] == "specification.docx"
    assert doc["format"] == "docx"
    assert doc["media_type"] == DOCX_MIME
    assert doc["size_bytes"] == len(docx_bytes)

    ext = data["extraction"]
    assert "Project Overview" in ext["text"]
    assert "Technical Architecture" in ext["text"]
    assert ext["page_count"] is None
    assert ext["character_count"] > 0
    assert ext["word_count"] == 4


def test_extract_docx_with_table(client: TestClient) -> None:
    """DOCX with tables extracts structured table rows separated by pipes."""
    table = [["Phase", "Status"], ["Phase 1", "Completed"], ["Phase 2", "Done"]]
    docx_bytes = create_text_docx(["Roadmap Section"], table_rows=table)
    files = {"file": ("roadmap.docx", docx_bytes, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 200
    data = response.json()
    text = data["extraction"]["text"]

    assert "Roadmap Section" in text
    assert "Phase | Status" in text
    assert "Phase 1 | Completed" in text
    assert "Phase 2 | Done" in text


def test_extract_blank_docx_no_text_returns_422(client: TestClient) -> None:
    """A blank DOCX document returns HTTP 422 NO_EXTRACTABLE_TEXT."""
    blank = create_blank_docx()
    files = {"file": ("blank.docx", blank, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "NO_EXTRACTABLE_TEXT"


def test_extract_corrupted_docx_returns_422(client: TestClient) -> None:
    """A corrupted DOCX archive returns HTTP 422 INVALID_DOCUMENT."""
    corrupted = create_corrupted_docx()
    files = {"file": ("broken.docx", corrupted, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_DOCUMENT"


def test_extract_encrypted_docx_returns_422(client: TestClient) -> None:
    """An encrypted OLE2 DOCX file returns HTTP 422 ENCRYPTED_DOCUMENT."""
    encrypted = create_encrypted_docx()
    files = {"file": ("locked.docx", encrypted, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "ENCRYPTED_DOCUMENT"


def test_extract_zip_missing_document_xml_returns_415(
    client: TestClient,
) -> None:
    """A ZIP file named .docx without word/document.xml returns HTTP 415."""
    fake_zip = create_zip_without_document_xml()
    files = {"file": ("not_a_doc.docx", fake_zip, DOCX_MIME)}

    response = client.post("/api/v1/documents/extract", files=files)

    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
