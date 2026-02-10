"""
API routes module.
"""

from .supplier import router as supplier_router
from .documents import router as documents_router
from .admin import router as admin_router
from .analytics import router as analytics_router
from .vendor_auth import router as vendor_auth_router
from .reports import router as reports_router
from .audit import router as audit_router
from .notifications import router as notifications_router
from .messages import router as messages_router
from .timeline import router as timeline_router
from .expiry import router as expiry_router
from .profile_changes import router as profile_changes_router
from .user_management import router as user_management_router

__all__ = [
    "supplier_router",
    "documents_router",
    "admin_router",
    "analytics_router",
    "vendor_auth_router",
    "reports_router",
    "audit_router",
    "notifications_router",
    "messages_router",
    "timeline_router",
    "expiry_router",
    "profile_changes_router",
    "user_management_router",
]
