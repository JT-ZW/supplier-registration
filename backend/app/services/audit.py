"""
Audit logging service for tracking system activities.
"""

from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime
from fastapi import Request
import asyncio

from ..models.audit import (
    AuditAction,
    AuditResourceType,
    AuditLogCreateRequest,
    AUDIT_ACTION_LABELS,
)
from ..db.supabase import db


class AuditService:
    """Service for creating and managing audit logs."""
    
    async def log_action(
        self,
        action: AuditAction,
        resource_type: AuditResourceType,
        user_id: Optional[str] = None,
        user_type: str = "system",
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
    ) -> bool:
        """
        Create an audit log entry.
        
        Args:
            action: The action being performed
            resource_type: Type of resource being affected
            user_id: ID of user performing action
            user_type: Type of user (admin, vendor, system)
            resource_id: ID of the resource
            resource_name: Name/identifier of the resource
            changes: Dictionary of changes (for updates)
            metadata: Additional context
            ip_address: IP address of request
            user_agent: User agent string
            request_path: API endpoint path
            request_method: HTTP method
            
        Returns:
            bool: True if audit log created successfully
        """
        try:
            audit_data = {
                "user_type": user_type,
                "action": action.value,
                "action_description": AUDIT_ACTION_LABELS.get(action, action.value),
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "resource_name": resource_name,
                "changes": changes,
                "metadata": metadata,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "request_path": request_path,
                "request_method": request_method,
            }
            
            # Set admin_id or supplier_id based on user_type
            if user_type == "admin":
                audit_data["admin_id"] = user_id
                audit_data["supplier_id"] = None
            elif user_type == "vendor":
                audit_data["admin_id"] = None
                audit_data["supplier_id"] = user_id
            else:  # system
                audit_data["admin_id"] = None
                audit_data["supplier_id"] = None
            
            # Create audit log asynchronously
            await db.create_audit_log(audit_data)
            return True
            
        except Exception as e:
            # Don't let audit logging failures break the main flow
            print(f"⚠️ Failed to create audit log: {str(e)}")
            return False
    
    async def log_action_from_request(
        self,
        request: Request,
        action: AuditAction,
        resource_type: AuditResourceType,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        current_user: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create an audit log entry from a FastAPI request.
        
        Args:
            request: FastAPI Request object
            action: The action being performed
            resource_type: Type of resource being affected
            resource_id: ID of the resource
            resource_name: Name/identifier of the resource
            changes: Dictionary of changes
            metadata: Additional context
            current_user: Current authenticated user dict
            
        Returns:
            bool: True if audit log created successfully
        """
        # Extract user information
        user_id = None
        user_type = "system"
        
        if current_user:
            user_id = current_user.get("id")
            # Determine user type based on current_user structure
            if "role" in current_user:  # Admin user
                user_type = "admin"
            elif "company_name" in current_user:  # Vendor/Supplier
                user_type = "vendor"
        
        # Extract request information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        request_path = str(request.url.path)
        request_method = request.method
        
        return await self.log_action(
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            user_type=user_type,
            resource_id=resource_id,
            resource_name=resource_name,
            changes=changes,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
        )
    
    def audit_log(
        self,
        action: AuditAction,
        resource_type: AuditResourceType,
        get_resource_id: Optional[Callable] = None,
        get_resource_name: Optional[Callable] = None,
        get_changes: Optional[Callable] = None,
        get_metadata: Optional[Callable] = None,
    ):
        """
        Decorator for automatically auditing route actions.
        
        Usage:
            @audit_log(
                action=AuditAction.SUPPLIER_APPROVED,
                resource_type=AuditResourceType.SUPPLIER,
                get_resource_id=lambda kwargs: kwargs.get('supplier_id'),
                get_resource_name=lambda result: result.get('company_name'),
            )
            async def approve_supplier(supplier_id: str, ...):
                ...
        
        Args:
            action: The action being performed
            resource_type: Type of resource being affected
            get_resource_id: Function to extract resource ID from kwargs
            get_resource_name: Function to extract resource name from result
            get_changes: Function to extract changes from kwargs/result
            get_metadata: Function to extract metadata from kwargs/result
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract request and current_user from kwargs if available
                request = kwargs.get("request")
                current_user = kwargs.get("current_admin") or kwargs.get("current_user")
                
                # Execute the original function
                result = await func(*args, **kwargs)
                
                # Extract audit information
                resource_id = get_resource_id(kwargs) if get_resource_id else None
                resource_name = get_resource_name(result) if get_resource_name else None
                changes = get_changes(kwargs, result) if get_changes else None
                metadata = get_metadata(kwargs, result) if get_metadata else None
                
                # Create audit log (don't await to avoid slowing down response)
                if request:
                    asyncio.create_task(
                        self.log_action_from_request(
                            request=request,
                            action=action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            resource_name=resource_name,
                            changes=changes,
                            metadata=metadata,
                            current_user=current_user,
                        )
                    )
                
                return result
            
            return wrapper
        return decorator


# Global instance
audit_service = AuditService()


# Convenience function for manual logging
async def log_audit(
    action: AuditAction,
    resource_type: AuditResourceType,
    user_id: Optional[str] = None,
    user_type: str = "system",
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Convenience function for creating audit logs.
    
    Usage:
        await log_audit(
            action=AuditAction.SUPPLIER_APPROVED,
            resource_type=AuditResourceType.SUPPLIER,
            user_id=admin_id,
            user_type="admin",
            resource_id=supplier_id,
            resource_name="ABC Company Ltd",
        )
    """
    return await audit_service.log_action(
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        user_type=user_type,
        resource_id=resource_id,
        resource_name=resource_name,
        changes=changes,
        metadata=metadata,
    )
