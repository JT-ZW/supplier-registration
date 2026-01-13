"""
API dependencies for authentication and common utilities.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.security import verify_access_token
from ..db.supabase import db, Database
from ..models import AdminResponse


# HTTP Bearer token security scheme
security = HTTPBearer()


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
    
    admin = await db.get_admin_by_id(admin_id)
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
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ):
        self.search = search
        self.status = status
        self.category = category
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.ascending = sort_order.lower() == "asc"
