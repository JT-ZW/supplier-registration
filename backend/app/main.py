"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from .core.config import settings
from .core.logger import logger, log_error
from .middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    AccountLockoutMiddleware
)
from .api.routes import (
    supplier_router,
    documents_router,
    admin_router,
    analytics_router,
    vendor_auth_router,
    reports_router,
    audit_router,
    notifications_router,
    messages_router,
    timeline_router,
    expiry_router,
    profile_changes_router,
    user_management_router,
)
from .models import HealthCheckResponse, ValidationErrorResponse, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"API Version: {settings.API_VERSION}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="API for Supplier Registration and Approval System",
    version=settings.API_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ============== Middleware ==============

# Security Headers Middleware (add first for all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Request Size Limit Middleware (prevent memory exhaustion)
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_size_mb=25  # 25MB max request size
)

# Rate Limiting Middleware (prevent brute force and DDoS)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,  # 60 requests per minute per IP
    burst_limit=100  # 100 requests burst limit
)

# Account Lockout Middleware (prevent brute force on login)
app.add_middleware(
    AccountLockoutMiddleware,
    max_attempts=5,  # Lock after 5 failed attempts
    lockout_duration_minutes=15  # Lock for 15 minutes
)

# GZip Compression Middleware
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses larger than 1KB
    compresslevel=6     # Balance between compression ratio and speed
)

# CORS Middleware (configured for security)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
    ] if not settings.DEBUG else [
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # Explicit methods
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],  # Explicit headers
    max_age=3600,  # Cache preflight requests for 1 hour
)


# ============== Exception Handlers ==============

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    # Log validation error without exposing sensitive data
    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error_count": len(exc.errors())
        }
    )
    
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ValidationErrorResponse(
            success=False,
            error="Validation Error",
            errors=errors
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    # Log error with full details for debugging
    log_error(
        exc,
        context={
            "method": request.method,
            "path": request.url.path,
            "client_host": request.client.host if request.client else None
        }
    )
    
    # SECURITY: Never expose internal error details to client
    # Even in debug mode, return generic error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            error="An unexpected error occurred. Please try again later.",
            error_code="INTERNAL_ERROR"
        ).model_dump()
    )


# ============== Routes ==============

@app.get(
    "/",
    response_model=dict,
    tags=["Root"]
)
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.API_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/docs" if settings.DEBUG else "unavailable",
    }


@app.get(
    f"/{settings.API_VERSION}/health",
    response_model=HealthCheckResponse,
    tags=["Health"]
)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version=settings.API_VERSION,
        environment=settings.APP_ENV,
        database="connected",
        storage="connected",
    )


# Include routers
app.include_router(
    supplier_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    documents_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    admin_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    analytics_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    vendor_auth_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    reports_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    audit_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    notifications_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    messages_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    timeline_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    expiry_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    profile_changes_router,
    prefix=f"/api/{settings.API_VERSION}"
)

app.include_router(
    user_management_router,
    prefix=f"/api/{settings.API_VERSION}"
)


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )
