"""
API dependencies for authentication and common utilities.
"""

import asyncio
import time
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.security import verify_access_token
from ..db.supabase import db, Database
from ..models import AdminResponse, AdminRole


# HTTP Bearer token security scheme
security = HTTPBearer()


# Short-lived in-process admin cache to reduce repetitive auth lookups
# when the dashboard fires several concurrent requests.
_ADMIN_CACHE_TTL_SECONDS = 15
_admin_cache_lock = asyncio.Lock()
_admin_cache: dict[str, tuple[float, dict]] = {}


async def _get_cached_admin(admin_id: str) -> Optional[dict]:
    async with _admin_cache_lock:
        cached = _admin_cache.get(admin_id)
        if not cached:
            return None

        expires_at, admin = cached
        if time.time() >= expires_at:
            _admin_cache.pop(admin_id, None)
            return None

        return admin


async def _set_cached_admin(admin_id: str, admin: dict) -> None:
    async with _admin_cache_lock:
        _admin_cache[admin_id] = (time.time() + _ADMIN_CACHE_TTL_SECONDS, admin)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated admin user.
    
    Args:
        credentials: Bearer token credentials
        
    Returns:
        Admin user data from database
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = verify_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin = await _get_cached_admin(admin_id)
    if admin is None:
        admin = await db.get_admin_by_id(admin_id)
        if admin:
            await _set_cached_admin(admin_id, admin)

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin user not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not admin.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated",
        )
    
    return admin


async def require_system_admin(
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Dependency to ensure the current admin has SYSTEM_ADMIN role.
    
    Args:
        admin: Current authenticated admin from get_current_admin
        
    Returns:
        Admin user data
        
    Raises:
        HTTPException: If admin does not have SYSTEM_ADMIN role
    """
    if admin.get("role") != AdminRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires System Administrator privileges",
        )
    
    return admin


async def get_optional_admin(
    request: Request
) -> Optional[dict]:
    """
    Dependency to optionally get the current admin if authenticated.
    Returns None if no valid authentication is provided.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    payload = verify_access_token(token)
    
    if payload is None:
        return None
    
    admin_id = payload.get("sub")
    if not admin_id:
        return None
    
    return await db.get_admin_by_id(admin_id)


async def get_current_vendor(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated vendor/supplier user.
    Accepts tokens with role == "vendor" (7-day vendor tokens) issued by
    the vendor auth routes.
    """
    token = credentials.credentials
    payload = verify_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject admin tokens presented to vendor endpoints
    if payload.get("role") != "vendor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token role",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplier_id = payload.get("sub")
    if not supplier_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    supplier = await db.get_supplier_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vendor user not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return supplier


def get_client_ip(request: Request) -> str:
    """
    Get the client IP address from request.
    Handles X-Forwarded-For header for proxied requests.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Get user agent from request headers."""
    return request.headers.get("User-Agent", "unknown")


class PaginationParams:
    """Pagination parameters as a dependency."""
    
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20
    ):
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        if page_size > 100:
            page_size = 100
            
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


class FilterParams:
    """Common filter parameters as a dependency."""
    
    def __init__(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        company_name: Optional[str] = None,
        email: Optional[str] = None,
        contact_person: Optional[str] = None,
        registration_number: Optional[str] = None,
        tax_id: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "submitted_at",
        sort_order: str = "desc"
    ):
        self.search = search
        self.status = status
        self.category = category
        self.company_name = company_name
        self.email = email
        self.contact_person = contact_person
        self.registration_number = registration_number
        self.tax_id = tax_id
        self.phone = phone
        self.city = city
        self.country = country
        self.date_from = date_from
        self.date_to = date_to
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.ascending = sort_order.lower() == "asc"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get either an admin or vendor user.
    """
    token = credentials.credentials
    payload = verify_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Note: Because both IDs are UUIDs, we check admin first, then vendor.
    admin = await db.get_admin_by_id(user_id)
    if admin:
        if not admin.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is deactivated",
            )
        return {"type": "admin", "data": admin}

    supplier = await db.get_supplier_by_id(user_id)
    if supplier:
        return {"type": "vendor", "data": supplier}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User not found",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP address from request.
    Checks X-Forwarded-For header first (for proxies), then falls back to client host.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        IP address as string or None
    """
    # Check X-Forwarded-For header (for proxied requests)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client host
    if request.client:
        return request.client.host
    
    return None

