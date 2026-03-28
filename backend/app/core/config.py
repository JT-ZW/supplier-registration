"""
Application configuration settings.
Uses pydantic-settings for type-safe environment variable handling.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Supplier Registration System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    
    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AWS S3 (Optional - Using Supabase Storage as primary)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "supplier-documents"
    S3_PRESIGNED_URL_EXPIRY: int = 600  # 10 minutes
    
    # File Upload
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_FILE_TYPES: str = "application/pdf,image/jpeg,image/png,image/jpg"
    
    @property
    def allowed_file_types_list(self) -> List[str]:
        """Return allowed file types as a list."""
        return [ft.strip() for ft in self.ALLOWED_FILE_TYPES.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        """Return max file size in bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
    
    # Email (SendGrid)
    SENDGRID_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "noreply@yourcompany.com"
    FROM_NAME: str = "Supplier Registration System"
    ADMIN_EMAIL: str = "admin@yourcompany.com"  # Admin email for notifications
    
    # Email (SMTP Alternative)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # Frontend URL
    FRONTEND_URL: str = "http://localhost:3000"

    # Performance and caching
    REDIS_URL: Optional[str] = None
    ANALYTICS_CACHE_TTL_SECONDS: int = 45
    SLOW_REQUEST_THRESHOLD_MS: int = 800
    
    # Data Retention
    REJECTED_APPLICATION_RETENTION_DAYS: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields in .env without validation errors


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Using lru_cache ensures settings are only loaded once.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
