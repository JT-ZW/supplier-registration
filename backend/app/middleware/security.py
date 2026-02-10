"""
Security middleware for rate limiting, security headers, and request validation.
"""

import time
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.logger import logger, log_security_event


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent brute force and DDoS attacks.
    
    Implements sliding window rate limiting per IP address.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_limit: int = 100
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        
        # Store request timestamps per IP
        # Format: {ip: [(timestamp1, timestamp2, ...)]}
        self.request_counts: Dict[str, list] = defaultdict(list)
        
        # Store locked out IPs
        # Format: {ip: lockout_until_timestamp}
        self.lockouts: Dict[str, float] = {}
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _is_whitelisted(self, path: str) -> bool:
        """Check if path should bypass rate limiting."""
        # Health check and static files bypass rate limiting
        whitelist = ["/health", "/docs", "/redoc", "/openapi.json"]
        return any(path.startswith(wl) for wl in whitelist)
    
    def _clean_old_requests(self, ip: str, current_time: float):
        """Remove requests older than 1 minute."""
        cutoff_time = current_time - 60
        self.request_counts[ip] = [
            ts for ts in self.request_counts[ip]
            if ts > cutoff_time
        ]
    
    def _check_rate_limit(self, ip: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if IP has exceeded rate limit.
        
        Returns:
            Tuple of (is_allowed, headers_dict)
        """
        current_time = time.time()
        
        # Check if IP is locked out
        if ip in self.lockouts:
            lockout_until = self.lockouts[ip]
            if current_time < lockout_until:
                remaining = int(lockout_until - current_time)
                return False, {
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(lockout_until)),
                    "Retry-After": str(remaining)
                }
            else:
                # Lockout expired
                del self.lockouts[ip]
                self.request_counts[ip] = []
        
        # Clean old requests
        self._clean_old_requests(ip, current_time)
        
        # Count requests in the last minute
        request_count = len(self.request_counts[ip])
        
        # Check burst limit (fast consecutive requests)
        if request_count >= self.burst_limit:
            # Lock out for 5 minutes
            lockout_until = current_time + 300
            self.lockouts[ip] = lockout_until
            
            log_security_event(
                "rate_limit_burst_exceeded",
                {
                    "ip": ip,
                    "request_count": request_count,
                    "lockout_until": lockout_until
                },
                severity="WARNING"
            )
            
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(lockout_until)),
                "Retry-After": "300"
            }
        
        # Check normal rate limit
        if request_count >= self.requests_per_minute:
            reset_time = min(self.request_counts[ip]) + 60
            
            log_security_event(
                "rate_limit_exceeded",
                {
                    "ip": ip,
                    "request_count": request_count,
                    "reset_time": reset_time
                },
                severity="WARNING"
            )
            
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time)),
                "Retry-After": str(int(reset_time - current_time))
            }
        
        # Allow request
        self.request_counts[ip].append(current_time)
        
        remaining = self.requests_per_minute - (request_count + 1)
        reset_time = current_time + 60
        
        return True, {
            "X-RateLimit-Limit": str(self.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time))
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting."""
        # Skip rate limiting for whitelisted paths
        if self._is_whitelisted(request.url.path):
            return await call_next(request)
        
        ip = self._get_client_ip(request)
        
        # Check rate limit
        is_allowed, headers = self._check_rate_limit(ip)
        
        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too many requests",
                    "message": "Rate limit exceeded. Please try again later."
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    
    Implements OWASP recommended security headers.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Enforce HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:;"
        )
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=()"
        )
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit maximum request body size to prevent memory exhaustion.
    """
    
    def __init__(self, app: ASGIApp, max_size_mb: int = 25):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing."""
        # Get content length from headers
        content_length = request.headers.get("Content-Length")
        
        if content_length:
            content_length = int(content_length)
            
            if content_length > self.max_size_bytes:
                log_security_event(
                    "request_size_exceeded",
                    {
                        "content_length": content_length,
                        "max_allowed": self.max_size_bytes,
                        "path": request.url.path
                    },
                    severity="WARNING"
                )
                
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": "Request too large",
                        "message": f"Request body exceeds maximum size of {self.max_size_bytes // (1024 * 1024)}MB"
                    }
                )
        
        return await call_next(request)


class AccountLockoutMiddleware(BaseHTTPMiddleware):
    """
    Track failed login attempts and enforce account lockout.
    
    Prevents brute force attacks on authentication endpoints.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        max_attempts: int = 5,
        lockout_duration_minutes: int = 15
    ):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration_minutes * 60
        
        # Track failed attempts per identifier (email or IP)
        # Format: {identifier: [timestamp1, timestamp2, ...]}
        self.failed_attempts: Dict[str, list] = defaultdict(list)
        
        # Track locked accounts
        # Format: {identifier: lockout_until_timestamp}
        self.lockouts: Dict[str, float] = {}
    
    def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if account/IP is locked out.
        
        Returns:
            Tuple of (is_locked, seconds_until_unlock)
        """
        if identifier in self.lockouts:
            current_time = time.time()
            lockout_until = self.lockouts[identifier]
            
            if current_time < lockout_until:
                remaining = int(lockout_until - current_time)
                return True, remaining
            else:
                # Lockout expired
                del self.lockouts[identifier]
                self.failed_attempts[identifier] = []
        
        return False, 0
    
    def record_failed_attempt(self, identifier: str):
        """Record a failed login attempt."""
        current_time = time.time()
        
        # Remove attempts older than lockout duration
        cutoff_time = current_time - self.lockout_duration
        self.failed_attempts[identifier] = [
            ts for ts in self.failed_attempts[identifier]
            if ts > cutoff_time
        ]
        
        # Add new failed attempt
        self.failed_attempts[identifier].append(current_time)
        
        # Check if should lock out
        if len(self.failed_attempts[identifier]) >= self.max_attempts:
            lockout_until = current_time + self.lockout_duration
            self.lockouts[identifier] = lockout_until
            
            log_security_event(
                "account_locked_brute_force",
                {
                    "identifier": identifier,
                    "failed_attempts": len(self.failed_attempts[identifier]),
                    "lockout_until": lockout_until
                },
                severity="CRITICAL"
            )
    
    def clear_failed_attempts(self, identifier: str):
        """Clear failed attempts on successful login."""
        if identifier in self.failed_attempts:
            del self.failed_attempts[identifier]
        if identifier in self.lockouts:
            del self.lockouts[identifier]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through account lockout middleware."""
        # Only check login endpoints
        if "/login" not in request.url.path.lower():
            return await call_next(request)
        
        # For login endpoints, the actual lockout check happens in the route handler
        # This middleware just provides the infrastructure
        
        return await call_next(request)


# Export middleware classes
__all__ = [
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "RequestSizeLimitMiddleware",
    "AccountLockoutMiddleware"
]
