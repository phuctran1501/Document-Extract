"""Unit tests for structured logging and Zero Document Logging security (NFR-01)."""

import json
import logging

import pytest

from app.core.config import Settings
from app.core.correlation import set_correlation_id
from app.core.logging import (
    StructuredJsonFormatter,
    StructuredTextFormatter,
    setup_logging,
)
from app.services.document_service import DocumentService
from tests.docx_helpers import create_text_docx
from tests.pdf_helpers import create_text_pdf


def test_structured_json_formatter_fields() -> None:
    """StructuredJsonFormatter outputs valid JSON with standard and extra attributes."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with extra metadata",
        args=(),
        exc_info=None,
    )
    record.custom_field = "custom_value"  # type: ignore[attr-defined]

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test message with extra metadata"
    assert "timestamp" in parsed
    assert parsed["custom_field"] == "custom_value"


def test_structured_json_formatter_with_correlation_id() -> None:
    """StructuredJsonFormatter automatically includes the active correlation ID."""
    set_correlation_id("test-corr-id-12345")
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=20,
        msg="Warning event",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["correlation_id"] == "test-corr-id-12345"


def test_structured_json_formatter_with_exception() -> None:
    """StructuredJsonFormatter formats exception traces into the JSON object."""
    formatter = StructuredJsonFormatter()
    try:
        raise ValueError("Simulated failure")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=30,
        msg="An error occurred",
        args=(),
        exc_info=exc_info,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert "exception" in parsed
    assert "ValueError: Simulated failure" in parsed["exception"]


def test_structured_text_formatter() -> None:
    """StructuredTextFormatter formats human-readable lines with correlation ID."""
    set_correlation_id("test-text-corr")
    formatter = StructuredTextFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=15,
        msg="Readable test log",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "[INFO   ]" in output
    assert "[test-text-corr]" in output
    assert "app.test: Readable test log" in output


def test_setup_logging_configuration() -> None:
    """setup_logging configures root logger handlers and levels."""
    settings = Settings(log_level="DEBUG", log_json_format=True)
    setup_logging(settings)

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1
    assert isinstance(root.handlers[0].formatter, StructuredJsonFormatter)


@pytest.mark.anyio
async def test_zero_document_logging_security_pdf(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Extracted PDF text is NEVER logged, satisfying NFR-01 Zero Document Logging."""
    canary_text = "CONFIDENTIAL_CANARY_SALARY_99999_USD"
    pdf_bytes = create_text_pdf([canary_text])

    service = DocumentService()
    with caplog.at_level(logging.DEBUG):
        response = await service.process_document_upload("resume.pdf", pdf_bytes)

    # Verify extraction succeeded and contains canary text
    assert canary_text in response.extraction.text

    # Verify that NO log record contains the canary text
    for record in caplog.records:
        assert canary_text not in record.getMessage()
        # Verify custom attributes do not leak the text
        for val in record.__dict__.values():
            assert canary_text not in str(val)

    assert canary_text not in caplog.text


@pytest.mark.anyio
async def test_zero_document_logging_security_docx(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Extracted DOCX text is NEVER logged, satisfying NFR-01 Zero Document Logging."""
    canary_text = "TOP_SECRET_PASSPHRASE_CANARY_DOCX"
    docx_bytes = create_text_docx([canary_text])

    service = DocumentService()
    with caplog.at_level(logging.DEBUG):
        response = await service.process_document_upload("cv.docx", docx_bytes)

    assert canary_text in response.extraction.text

    for record in caplog.records:
        assert canary_text not in record.getMessage()
        for val in record.__dict__.values():
            assert canary_text not in str(val)

    assert canary_text not in caplog.text
