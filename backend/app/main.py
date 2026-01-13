"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from .core.config import settings
from .api.routes import (
    supplier_router,
    documents_router,
    admin_router,
    analytics_router,
    vendor_auth_router,
)
from .models import HealthCheckResponse, ValidationErrorResponse, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME}")
    print(f"📝 Environment: {settings.APP_ENV}")
    print(f"🔗 API Version: {settings.API_VERSION}")
    
    yield
    
    # Shutdown
    print(f"👋 Shutting down {settings.APP_NAME}")


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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ] if settings.DEBUG else [settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Exception Handlers ==============

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    # DEBUG: Log the validation errors
    print(f"❌ VALIDATION ERROR on {request.method} {request.url.path}")
    print(f"   Body: {exc.body}")
    print(f"   Errors:")
    for error in exc.errors():
        print(f"      - {error}")
    
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
    if settings.DEBUG:
        # In debug mode, show detailed error
        import traceback
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error="Internal Server Error",
                error_code="INTERNAL_ERROR",
                details={
                    "message": str(exc),
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                }
            ).model_dump()
        )
    else:
        # In production, show generic error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error="An unexpected error occurred",
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
