"""Bounded stream reading utility to enforce maximum upload size constraints."""

from fastapi import UploadFile

from app.core.errors import AppException

DEFAULT_CHUNK_SIZE_BYTES = 64 * 1024  # 64 KiB chunks


async def read_upload_file_bounded(
    file: UploadFile,
    max_bytes: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> bytes:
    """Read an uploaded file in chunks up to max_bytes.

    Aborts immediately and raises an AppException (HTTP 413) as soon as
    accumulated bytes exceed max_bytes, preventing unbounded memory
    consumption from malicious or oversized upload streams.

    Args:
        file: The FastAPI/Starlette UploadFile instance.
        max_bytes: The maximum number of bytes allowed.
        chunk_size: The chunk size in bytes to read incrementally.

    Returns:
        bytes: The complete raw binary content of the file.

    Raises:
        AppException: If the file size exceeds max_bytes (HTTP 413).
    """
    chunks: list[bytes] = []
    total_bytes = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break

        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise AppException(
                status_code=413,
                code="FILE_TOO_LARGE",
                message=(
                    f"File size exceeds the maximum allowed limit of {max_bytes} bytes."
                ),
            )
        chunks.append(chunk)

    return b"".join(chunks)
