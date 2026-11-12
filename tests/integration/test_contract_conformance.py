"""Integration tests verifying API Contract conformance for ASP.NET Core."""

from fastapi.testclient import TestClient

from app.core.correlation import CORRELATION_ID_HEADER
from tests.docx_helpers import create_encrypted_docx
from tests.pdf_helpers import (
    create_blank_pdf,
    create_corrupted_pdf,
    create_non_pdf_file,
    create_text_pdf,
)


def test_openapi_schema_conformance(client: TestClient) -> None:
    """OpenAPI schema contains all documented endpoints, operations, and schemas."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    assert schema["info"]["title"] == "DocuExtract"
    assert schema["info"]["version"] == "0.1.0"

    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/v1/documents/extract" in paths
    assert "/api/v1/text/analyze" in paths

    # Verify extract endpoint metadata
    extract_op = paths["/api/v1/documents/extract"]["post"]
    req_body = extract_op["requestBody"]["content"]
    assert "multipart/form-data" in req_body


def test_correlation_id_round_trip_preserved(client: TestClient) -> None:
    """Client X-Correlation-ID is preserved and returned in response headers."""
    client_corr_id = "aspnet-core-client-id-789abc"
    headers = {CORRELATION_ID_HEADER: client_corr_id}

    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get(CORRELATION_ID_HEADER) == client_corr_id


def test_correlation_id_auto_generated_when_omitted(client: TestClient) -> None:
    """When client omits X-Correlation-ID, server generates a hex correlation ID."""
    response = client.get("/health")
    assert response.status_code == 200
    generated_id = response.headers.get(CORRELATION_ID_HEADER)
    assert generated_id is not None
    assert len(generated_id) >= 16


def test_error_envelope_consistency_with_correlation_id(
    client: TestClient,
) -> None:
    """Error responses return envelope containing the matching correlation ID."""
    client_corr_id = "trace-err-id-456def"
    headers = {CORRELATION_ID_HEADER: client_corr_id}

    # Upload empty file to trigger 400 INVALID_REQUEST
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/api/v1/documents/extract", files=files, headers=headers)

    assert response.status_code == 400
    assert response.headers.get(CORRELATION_ID_HEADER) == client_corr_id

    body = response.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "INVALID_REQUEST"
    assert err["correlation_id"] == client_corr_id
    assert len(err["message"]) > 0


def test_contract_error_codes_match_documented_specification(
    client: TestClient,
) -> None:
    """All error codes and HTTP statuses match the contract table in api-contract.md."""
    # 1. 400 INVALID_REQUEST (Empty file)
    r_empty = client.post(
        "/api/v1/documents/extract",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r_empty.status_code == 400
    assert r_empty.json()["error"]["code"] == "INVALID_REQUEST"

    # 2. 415 UNSUPPORTED_FILE_TYPE (Unsupported extension)
    r_ext = client.post(
        "/api/v1/documents/extract",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert r_ext.status_code == 415
    assert r_ext.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    # 3. 415 UNSUPPORTED_FILE_TYPE (Fake magic bytes)
    fake_pdf = create_non_pdf_file()
    r_fake = client.post(
        "/api/v1/documents/extract",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert r_fake.status_code == 415
    assert r_fake.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    # 4. 422 INVALID_DOCUMENT (Corrupted structure)
    broken_pdf = create_corrupted_pdf()
    r_broken = client.post(
        "/api/v1/documents/extract",
        files={"file": ("broken.pdf", broken_pdf, "application/pdf")},
    )
    assert r_broken.status_code == 422
    assert r_broken.json()["error"]["code"] == "INVALID_DOCUMENT"

    # 5. 422 ENCRYPTED_DOCUMENT (Password protected)
    locked_docx = create_encrypted_docx()
    r_locked = client.post(
        "/api/v1/documents/extract",
        files={
            "file": (
                "locked.docx",
                locked_docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r_locked.status_code == 422
    assert r_locked.json()["error"]["code"] == "ENCRYPTED_DOCUMENT"

    # 6. 422 NO_EXTRACTABLE_TEXT (Blank scanned-like PDF)
    blank_pdf = create_blank_pdf()
    r_blank = client.post(
        "/api/v1/documents/extract",
        files={"file": ("blank.pdf", blank_pdf, "application/pdf")},
    )
    assert r_blank.status_code == 422
    assert r_blank.json()["error"]["code"] == "NO_EXTRACTABLE_TEXT"


def test_successful_extraction_matches_contract_dto_structure(
    client: TestClient,
) -> None:
    """Extraction conforms exactly to DocumentExtractResponse DTO structure."""
    pdf_bytes = create_text_pdf(["Software Architecture Specification"])
    files = {"file": ("arch.pdf", pdf_bytes, "application/pdf")}

    response = client.post("/api/v1/documents/extract", files=files)
    assert response.status_code == 200
    data = response.json()

    # Document metadata block
    doc = data["document"]
    assert doc["filename"] == "arch.pdf"
    assert doc["format"] == "pdf"
    assert doc["media_type"] == "application/pdf"
    assert doc["size_bytes"] == len(pdf_bytes)

    # Extraction block
    ext = data["extraction"]
    assert "Software Architecture Specification" in ext["text"]
    assert ext["page_count"] == 1
    assert ext["character_count"] > 0
    assert ext["word_count"] == 3

    # Warnings block
    assert isinstance(data["warnings"], list)
