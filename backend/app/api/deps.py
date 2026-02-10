"""
API dependencies for authentication and common utilities.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.security import verify_access_token
from ..db.supabase import db, Database
from ..models import AdminResponse, AdminRole


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
    
    Args:
        credentials: Bearer token credentials
        
    Returns:
        Supplier user data from database
        
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
        sort_by: str = "created_at",
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
        self.sort_by = sort_by
        self.sort_order = sort_order
        self.ascending = sort_order.lower() == "asc"


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
