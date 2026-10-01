"""
EquiConnected Portal — FastAPI application entry point.
"""
import asyncio
from contextlib import asynccontextmanager

import os
import re

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


async def _recover_message_notifications() -> None:
    """Retry only unclaimed pending intents on a bounded interval."""
    logger = get_logger(__name__)
    while True:
        try:
            # Import lazily so email or database accounting issues cannot make
            # unrelated application startup depend on messaging delivery.
            from app.services.messaging_notifications import dispatch_pending

            await asyncio.to_thread(dispatch_pending, batch_size=20)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "messaging_notification_recovery_failed",
                error_type=type(exc).__name__,
            )
        await asyncio.sleep(30)


async def _cleanup_provider_contact_click_receipts() -> None:
    """Periodically purge one small batch of expired contact receipts."""
    logger = get_logger(__name__)
    while True:
        try:
            # Keep privacy cleanup independent of the email delivery worker;
            # the service owns a fresh SessionLocal session for each batch.
            from app.services.provider_insights_service import (
                CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE,
                CONTACT_CLICK_RECEIPT_CLEANUP_INTERVAL_SECONDS,
                cleanup_expired_contact_click_receipts_once,
            )

            await asyncio.to_thread(
                cleanup_expired_contact_click_receipts_once,
                batch_size=CONTACT_CLICK_RECEIPT_CLEANUP_BATCH_SIZE,
            )
            interval = CONTACT_CLICK_RECEIPT_CLEANUP_INTERVAL_SECONDS
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "provider_contact_click_receipt_cleanup_failed",
                error_type=type(exc).__name__,
            )
            interval = 60
        await asyncio.sleep(interval)


def _safe_log_path(request: Request) -> str:
    """Redact security tokens embedded in public invitation paths."""
    return re.sub(
        r"(/api/v1/provider/invitations/)[^/]+",
        r"\1<redacted>",
        request.url.path,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        log_level="DEBUG" if settings.DEBUG else "INFO",
        json_logs=settings.is_production,
    )
    logger = get_logger(__name__)
    logger.info(
        "startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    recovery_task = asyncio.create_task(_recover_message_notifications())
    contact_receipt_cleanup_task = asyncio.create_task(
        _cleanup_provider_contact_click_receipts()
    )
    try:
        yield
    finally:
        recovery_task.cancel()
        contact_receipt_cleanup_task.cancel()
        for task in (recovery_task, contact_receipt_cleanup_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        # Disable docs in production — API should be internal only
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Static file serving (uploaded photos, etc.) ───────────────────────────
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_v1_router)

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ):
        # Pydantic includes the rejected input by default. Omit it universally
        # so password fields in invite/setup/recovery requests are never echoed.
        errors = [
            {key: value for key, value in error.items() if key != "input"}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": errors}),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger = get_logger(__name__)
        logger.error(
            "unhandled_exception",
            path=_safe_log_path(request),
            method=request.method,
            # Private-message failures may contain decrypted values from a
            # dependency. Retain the error type, never its arbitrary payload.
            exc=type(exc).__name__ if request.url.path.startswith("/api/v1/messages") else str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
        )

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()
