"""Unit tests for bounded streaming upload reader."""

import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.errors import AppException
from app.core.streaming import read_upload_file_bounded


def _make_upload_file(content: bytes, filename: str = "test.pdf") -> UploadFile:
    """Create an UploadFile instance backed by in-memory BytesIO."""
    file_io = io.BytesIO(content)
    headers = Headers({"content-type": "application/pdf"})
    return UploadFile(file=file_io, filename=filename, headers=headers)


@pytest.mark.anyio
async def test_read_bounded_success() -> None:
    """Reading bytes within the limit returns exact content."""
    data = b"Hello, world! This is a test file."
    upload = _make_upload_file(data)

    result = await read_upload_file_bounded(upload, max_bytes=100, chunk_size=10)
    assert result == data


@pytest.mark.anyio
async def test_read_bounded_empty() -> None:
    """Empty upload returns empty bytes without error."""
    upload = _make_upload_file(b"")

    result = await read_upload_file_bounded(upload, max_bytes=100, chunk_size=10)
    assert result == b""


@pytest.mark.anyio
async def test_read_bounded_exact_limit() -> None:
    """Upload exactly at the max_bytes limit succeeds."""
    data = b"x" * 50
    upload = _make_upload_file(data)

    result = await read_upload_file_bounded(upload, max_bytes=50, chunk_size=10)
    assert result == data


@pytest.mark.anyio
async def test_read_bounded_exceeds_limit_aborts() -> None:
    """Upload exceeding max_bytes raises HTTP 413 FILE_TOO_LARGE immediately."""
    data = b"x" * 150
    upload = _make_upload_file(data)

    with pytest.raises(AppException) as exc_info:
        await read_upload_file_bounded(upload, max_bytes=100, chunk_size=10)

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert "exceeds the maximum allowed limit" in exc_info.value.message
