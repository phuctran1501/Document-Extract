# ==============================================================================
# DocuExtract Dockerfile (Python 3.12, Non-Root Runtime)
# ==============================================================================
FROM python:3.12-slim

# Prevent bytecode generation and configure unbuffered output for logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCUEXTRACT_HOST=0.0.0.0 \
    DOCUEXTRACT_PORT=8000

WORKDIR /app

# Create a non-root group and user (UID/GID 10001) for security hardening
RUN groupadd --gid 10001 appuser && \
    useradd --uid 10001 --gid 10001 --shell /bin/false --create-home appuser

# Install dependencies using pip without caching build wheels
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Copy application source code
COPY app/ app/

# Set file ownership for the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

EXPOSE 8000

# Container liveness health check targeting the lightweight /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

