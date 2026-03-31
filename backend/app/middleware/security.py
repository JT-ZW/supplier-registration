"""
Security middleware for rate limiting, security headers, and request validation.
"""

import time
from typing import Dict, Optional, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.logger import logger, log_security_event
from ..core.config import settings


async def _handle_disconnect_runtime_error(request: Request, exc: Exception) -> Response | None:
    """Return a benign response when the client disconnects during request processing."""
    if isinstance(exc, RuntimeError) and str(exc) == "No response returned.":
        try:
            disconnected = await request.is_disconnected()
        except Exception:
            disconnected = True

        if disconnected:
            logger.info(
                "Client disconnected before response: %s %s",
                request.method,
                request.url.path,
            )
            return Response(status_code=204)

    return None


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Capture request latency and log only slow requests."""

    def __init__(self, app: ASGIApp, slow_threshold_ms: int = 800):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            disconnect_response = await _handle_disconnect_runtime_error(request, exc)
            if disconnect_response is not None:
                return disconnect_response
            raise
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        if elapsed_ms >= self.slow_threshold_ms:
            logger.warning(
                "Slow request detected: %s %s (%d ms)",
                request.method,
                request.url.path,
                elapsed_ms,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "response_time_ms": elapsed_ms,
                    "slow_threshold_ms": self.slow_threshold_ms,
                    "client_ip": request.client.host if request.client else None,
                    "app_env": settings.APP_ENV,
                },
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using a sliding-window algorithm.

    Backend selection (decided once, lazily, on first request):
    - If ``settings.REDIS_URL`` is configured and Redis is reachable → Redis
      sorted-set sliding window (survives restarts, shared across workers).
    - Otherwise → in-process dict fallback (works with a single worker, resets
      on restart — acceptable for development / single-instance deployments).

    If Redis becomes unavailable mid-flight the middleware automatically falls
    back to in-memory and logs a warning.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_limit: int = 100,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit

        # Redis state (lazy-initialised on first request)
        self._redis: Optional[object] = None
        self._redis_available: Optional[bool] = None  # None = not yet tested

        # In-memory fallback state
        self.request_counts: Dict[str, list] = defaultdict(list)
        self.lockouts: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        whitelist = ["/health", "/docs", "/redoc", "/openapi.json"]
        return any(path.startswith(wl) for wl in whitelist)

    # ------------------------------------------------------------------
    # Redis backend
    # ------------------------------------------------------------------

    async def _get_redis(self) -> Optional[object]:
        """
        Return a live async Redis client, or None if Redis is not configured
        / not reachable.  The result is cached after the first probe.
        """
        if self._redis_available is False:
            return None
        if self._redis is not None:
            return self._redis
        if not settings.REDIS_URL:
            self._redis_available = False
            return None
        try:
            import redis.asyncio as aioredis  # lazy import — only needed when REDIS_URL is set
            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            await client.ping()
            self._redis = client
            self._redis_available = True
            logger.info("Rate limiter: Redis backend active (%s)", settings.REDIS_URL)
            return self._redis
        except Exception as exc:
            self._redis_available = False
            logger.warning(
                "Rate limiter: Redis unavailable (%s) — using in-memory fallback", exc
            )
            return None

    async def _check_rate_limit_redis(self, ip: str) -> Tuple[bool, Dict[str, str]]:
        """
        Sliding-window rate-limit check backed by Redis.

        Uses a sorted set keyed by ``rl:{ip}`` where each member's score is the
        request Unix timestamp.  A separate key ``rl_lock:{ip}`` (with a TTL)
        stores burst lockouts.

        All reads/writes are pipelined to minimise round-trips.
        """
        r = self._redis
        now = time.time()
        window_start = now - 60
        count_key = f"rl:{ip}"
        lock_key = f"rl_lock:{ip}"

        # Check lockout key first
        lock_ttl: int = await r.ttl(lock_key)
        if lock_ttl > 0:
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + lock_ttl)),
                "Retry-After": str(lock_ttl),
            }

        # Pipelined sliding-window operations:
        #   1. Remove timestamps outside the 60-second window
        #   2. Count timestamps still in window (BEFORE adding current)
        #   3. Add current timestamp
        #   4. Reset TTL so the key expires naturally
        pipe = r.pipeline()
        pipe.zremrangebyscore(count_key, "-inf", window_start)
        pipe.zcard(count_key)
        pipe.zadd(count_key, {str(now): now})
        pipe.expire(count_key, 70)  # slightly longer than the 60-s window
        results = await pipe.execute()

        count_before = results[1]  # ZCARD result = count before this request

        if count_before >= self.burst_limit:
            await r.setex(lock_key, 300, "1")
            log_security_event(
                "rate_limit_burst_exceeded",
                {"ip": ip, "request_count": count_before},
                severity="WARNING",
            )
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + 300)),
                "Retry-After": "300",
            }

        if count_before >= self.requests_per_minute:
            log_security_event(
                "rate_limit_exceeded",
                {"ip": ip, "request_count": count_before},
                severity="WARNING",
            )
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + 60)),
                "Retry-After": "60",
            }

        remaining = max(0, self.requests_per_minute - count_before - 1)
        return True, {
            "X-RateLimit-Limit": str(self.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + 60)),
        }

    # ------------------------------------------------------------------
    # In-memory fallback backend (original logic, unchanged)
    # ------------------------------------------------------------------

    def _clean_old_requests(self, ip: str, current_time: float) -> None:
        """Remove requests older than 1 minute from in-memory store."""
        cutoff = current_time - 60
        self.request_counts[ip] = [ts for ts in self.request_counts[ip] if ts > cutoff]

    def _check_rate_limit_memory(self, ip: str) -> Tuple[bool, Dict[str, str]]:
        """Sliding-window rate-limit check using in-process dicts."""
        current_time = time.time()

        # Check lockout
        if ip in self.lockouts:
            lockout_until = self.lockouts[ip]
            if current_time < lockout_until:
                remaining = int(lockout_until - current_time)
                return False, {
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(lockout_until)),
                    "Retry-After": str(remaining),
                }
            del self.lockouts[ip]
            self.request_counts[ip] = []

        self._clean_old_requests(ip, current_time)
        request_count = len(self.request_counts[ip])

        if request_count >= self.burst_limit:
            lockout_until = current_time + 300
            self.lockouts[ip] = lockout_until
            log_security_event(
                "rate_limit_burst_exceeded",
                {"ip": ip, "request_count": request_count, "lockout_until": lockout_until},
                severity="WARNING",
            )
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(lockout_until)),
                "Retry-After": "300",
            }

        if request_count >= self.requests_per_minute:
            reset_time = min(self.request_counts[ip]) + 60
            log_security_event(
                "rate_limit_exceeded",
                {"ip": ip, "request_count": request_count, "reset_time": reset_time},
                severity="WARNING",
            )
            return False, {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_time)),
                "Retry-After": str(int(reset_time - current_time)),
            }

        self.request_counts[ip].append(current_time)
        remaining = self.requests_per_minute - (request_count + 1)
        return True, {
            "X-RateLimit-Limit": str(self.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(current_time + 60)),
        }

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    async def _check_rate_limit(self, ip: str) -> Tuple[bool, Dict[str, str]]:
        """Dispatch to Redis or in-memory backend, with automatic fallback."""
        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                return await self._check_rate_limit_redis(ip)
            except Exception as exc:
                # Redis error mid-flight — degrade gracefully
                logger.warning(
                    "Redis rate-limit check failed (%s); falling back to in-memory", exc
                )
                self._redis = None
                self._redis_available = False

        return self._check_rate_limit_memory(ip)

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting."""
        if self._is_whitelisted(request.url.path):
            return await call_next(request)

        ip = self._get_client_ip(request)
        is_allowed, headers = await self._check_rate_limit(ip)

        if not is_allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too many requests",
                    "message": "Rate limit exceeded. Please try again later.",
                },
                headers=headers,
            )

        try:
            response = await call_next(request)
        except RuntimeError as exc:
            disconnect_response = await _handle_disconnect_runtime_error(request, exc)
            if disconnect_response is not None:
                return disconnect_response
            raise
        except Exception as exc:
            logger.error(
                "Unhandled error in route %s %s: %s",
                request.method,
                request.url.path,
                exc,
                exc_info=True,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "An unexpected error occurred. Please try again later."},
            )

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
        try:
            response = await call_next(request)
        except RuntimeError as exc:
            disconnect_response = await _handle_disconnect_runtime_error(request, exc)
            if disconnect_response is not None:
                return disconnect_response
            raise
        except Exception as exc:
            logger.error(
                f"Unhandled error in route {request.method} {request.url.path}: {exc}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "An unexpected error occurred. Please try again later."},
            )
        
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
            try:
                return await call_next(request)
            except RuntimeError as exc:
                disconnect_response = await _handle_disconnect_runtime_error(request, exc)
                if disconnect_response is not None:
                    return disconnect_response
                raise
        
        # For login endpoints, the actual lockout check happens in the route handler
        # This middleware just provides the infrastructure
        
        try:
            return await call_next(request)
        except RuntimeError as exc:
            disconnect_response = await _handle_disconnect_runtime_error(request, exc)
            if disconnect_response is not None:
                return disconnect_response
            raise


# Export middleware classes
__all__ = [
    "RequestTimingMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "RequestSizeLimitMiddleware",
    "AccountLockoutMiddleware"
]
