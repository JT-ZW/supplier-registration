"""
API routes module.
"""

from .supplier import router as supplier_router
from .documents import router as documents_router
from .admin import router as admin_router
from .analytics import router as analytics_router
from .vendor_auth import router as vendor_auth_router

__all__ = [
    "supplier_router",
    "documents_router",
    "admin_router",
    "analytics_router",
    "vendor_auth_router",
]
