"""
Structured logging configuration for the application.
Replaces print() statements with proper logging.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Create formatters
console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

# Create handlers
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(console_formatter)
console_handler.setLevel(logging.INFO)

# File handler for all logs
file_handler = logging.FileHandler(
    log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
)
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.DEBUG)

# File handler for errors only
error_handler = logging.FileHandler(
    log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
)
error_handler.setFormatter(file_formatter)
error_handler.setLevel(logging.ERROR)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_handler)

# Create application logger
logger = logging.getLogger("app")


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive data before logging.
    Removes passwords, tokens, API keys, etc.
    """
    sensitive_keys = {
        "password", "password_hash", "token", "refresh_token",
        "access_token", "api_key", "secret", "authorization",
        "credit_card", "ssn", "tax_id"
    }
    
    sanitized = {}
    for key, value in data.items():
        # Check if key contains sensitive information
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, str) and len(value) > 500:
            # Truncate very long strings
            sanitized[key] = value[:500] + "...[truncated]"
        else:
            sanitized[key] = value
    
    return sanitized


def log_request(
    method: str,
    path: str,
    ip_address: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
):
    """Log an API request."""
    logger.info(
        f"Request: {method} {path}",
        extra={
            "ip_address": ip_address,
            "user_id": user_id,
            **sanitize_log_data(kwargs)
        }
    )


def log_security_event(
    event_type: str,
    details: Dict[str, Any],
    severity: str = "WARNING"
):
    """Log a security-related event."""
    sanitized_details = sanitize_log_data(details)
    
    if severity == "CRITICAL":
        logger.critical(f"Security Event: {event_type}", extra=sanitized_details)
    elif severity == "ERROR":
        logger.error(f"Security Event: {event_type}", extra=sanitized_details)
    else:
        logger.warning(f"Security Event: {event_type}", extra=sanitized_details)


def log_auth_attempt(
    email: str,
    success: bool,
    ip_address: Optional[str] = None,
    reason: Optional[str] = None
):
    """Log an authentication attempt."""
    if success:
        logger.info(
            f"Auth Success: {email}",
            extra={"ip_address": ip_address}
        )
    else:
        logger.warning(
            f"Auth Failed: {email} - {reason or 'Unknown'}",
            extra={"ip_address": ip_address}
        )


def log_data_access(
    user_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    ip_address: Optional[str] = None
):
    """Log access to sensitive data."""
    logger.info(
        f"Data Access: {action} on {resource_type} {resource_id}",
        extra={
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "ip_address": ip_address
        }
    )


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
):
    """Log an error with context."""
    logger.error(
        f"Error: {type(error).__name__}: {str(error)}",
        extra=sanitize_log_data(context or {}),
        exc_info=True
    )


# Export logger instance
__all__ = [
    "logger",
    "log_request",
    "log_security_event",
    "log_auth_attempt",
    "log_data_access",
    "log_error",
    "sanitize_log_data"
]
