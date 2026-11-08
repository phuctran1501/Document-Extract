"""DocuExtract FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.text import router as text_router
from app.core.config import get_settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    """Create and configure the DocuExtract FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "A learning-first document processing microservice designed to extract "
            "and normalize text from documents for ASP.NET Core applications."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. Register middleware (Correlation ID)
    app.add_middleware(CorrelationIdMiddleware)

    # 2. Register exception handlers (API contract compliant error envelopes)
    register_exception_handlers(app)

    # 3. Register route handlers
    app.include_router(health_router)
    app.include_router(text_router, prefix=settings.api_v1_prefix)
    app.include_router(documents_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
