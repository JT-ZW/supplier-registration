"""
Supabase database client and utilities.
"""

from typing import Optional, Dict, Any, List
from postgrest import SyncPostgrestClient
from supabase_auth import SyncGoTrueClient

from ..core.config import settings


class SupabaseClient:
    """
    Minimal Supabase client that provides database and auth functionality.
    """
    def __init__(self, postgrest_client: SyncPostgrestClient, auth_client: SyncGoTrueClient):
        self.postgrest = postgrest_client
        self.auth = auth_client
    
    def table(self, table_name: str):
        """Access a table via PostgREST."""
        return self.postgrest.table(table_name)
    
    def rpc(self, function_name: str, params: Dict[str, Any] = None):
        """Call a PostgreSQL function via PostgREST RPC."""
        return self.postgrest.rpc(function_name, params or {})


class Database:
    """
    Database client wrapper for Supabase.
    Provides methods for common database operations.
    """
    
    _instance: Optional["Database"] = None
    _client: Optional[SupabaseClient] = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one database instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Supabase client."""
        if self._client is None:
            # Create PostgREST client
            postgrest_client = SyncPostgrestClient(
                base_url=f"{settings.SUPABASE_URL}/rest/v1",
                headers={
                    "apikey": settings.SUPABASE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}"
                }
            )
            
            # Create Auth client
            auth_client = SyncGoTrueClient(
                url=f"{settings.SUPABASE_URL}/auth/v1",
                headers={
                    "apikey": settings.SUPABASE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}"
                }
            )
            
            self._client = SupabaseClient(postgrest_client, auth_client)
    
    @property
    def client(self) -> SupabaseClient:
        """Get the Supabase client instance."""
        return self._client
    
    # ============== Supplier Operations ==============
    
    async def create_supplier(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new supplier record."""
        result = self._client.table("suppliers").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_supplier_by_id(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """Get a supplier by ID."""
        result = self._client.table("suppliers").select("*").eq("id", supplier_id).execute()
        return result.data[0] if result.data else None
    
    async def get_supplier_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a supplier by email (for duplicate checking)."""
        result = self._client.table("suppliers").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    async def update_supplier(self, supplier_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a supplier record."""
        self._client.table("suppliers").update(data).eq("id", supplier_id).execute()
        # Fetch updated record
        result = self._client.table("suppliers").select("*").eq("id", supplier_id).single().execute()
        return result.data if result.data else None
    
    async def delete_supplier(self, supplier_id: str) -> bool:
        """Delete a supplier record."""
        result = self._client.table("suppliers").delete().eq("id", supplier_id).execute()
        return len(result.data) > 0 if result.data else False
    
    async def list_suppliers(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        company_name: Optional[str] = None,
        email: Optional[str] = None,
        contact_person: Optional[str] = None,
        registration_number: Optional[str] = None,
        tax_id: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "created_at",
        ascending: bool = False
    ) -> Dict[str, Any]:
        """List suppliers with advanced filtering and pagination."""
        query = self._client.table("suppliers").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        if category:
            query = query.eq("business_category", category)
        
        # Advanced search filters
        if company_name:
            query = query.ilike("company_name", f"%{company_name}%")
        if email:
            query = query.ilike("email", f"%{email}%")
        if contact_person:
            query = query.ilike("contact_person_name", f"%{contact_person}%")
        if registration_number:
            query = query.ilike("registration_number", f"%{registration_number}%")
        if tax_id:
            query = query.ilike("tax_id", f"%{tax_id}%")
        if phone:
            query = query.ilike("phone", f"%{phone}%")
        if city:
            query = query.ilike("city", f"%{city}%")
        if country:
            query = query.ilike("country", f"%{country}%")
        
        # General search (legacy support)
        if search:
            query = query.or_(f"company_name.ilike.%{search}%,email.ilike.%{search}%,contact_person_name.ilike.%{search}%")
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.order(order_by, desc=not ascending).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total = result.count if result.count else 0
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "items": result.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    
    # ============== Document Operations ==============
    
    async def create_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new document record."""
        result = self._client.table("documents").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        result = self._client.table("documents").select("*").eq("id", document_id).execute()
        return result.data[0] if result.data else None
    
    async def get_documents_by_supplier(self, supplier_id: str) -> List[Dict[str, Any]]:
        """Get all documents for a supplier."""
        result = self._client.table("documents").select("*").eq("supplier_id", supplier_id).execute()
        return result.data
    
    async def update_document(self, document_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a document record."""
        result = self._client.table("documents").update(data).eq("id", document_id).execute()
        return result.data[0] if result.data else None
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document record."""
        self._client.table("documents").delete().eq("id", document_id).execute()
        return True
    
    async def delete_documents_by_supplier(self, supplier_id: str) -> bool:
        """Delete all documents for a supplier."""
        self._client.table("documents").delete().eq("supplier_id", supplier_id).execute()
        return True
    
    # ============== Admin Operations ==============
    
    async def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get an admin user by email."""
        result = self._client.table("admin_users").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None
    
    async def get_admin_by_id(self, admin_id: str) -> Optional[Dict[str, Any]]:
        """Get an admin user by ID."""
        result = self._client.table("admin_users").select("*").eq("id", admin_id).execute()
        return result.data[0] if result.data else None
    
    async def get_all_admins(self) -> List[Dict[str, Any]]:
        """Get all admin users."""
        result = self._client.table("admin_users").select("*").execute()
        return result.data if result.data else []
    
    async def get_active_admin_emails(self) -> List[Dict[str, str]]:
        """
        Get email addresses of all active admin users.
        
        Returns:
            List of dicts with 'email' and 'name' keys
        """
        result = self._client.table("admin_users")\
            .select("email, full_name")\
            .eq("is_active", True)\
            .execute()
        
        if not result.data:
            return []
        
        return [
            {
                "email": admin["email"],
                "name": admin.get("full_name", admin["email"])
            }
            for admin in result.data
        ]
    
    async def create_admin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new admin user."""
        result = self._client.table("admin_users").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def update_admin(self, admin_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an admin user."""
        result = self._client.table("admin_users").update(data).eq("id", admin_id).execute()
        return result.data[0] if result.data else None
    
    # ============== Audit Log Operations ==============
    
    async def create_audit_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an audit log entry."""
        result = self._client.table("audit_logs").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def list_audit_logs(
        self,
        admin_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """List audit logs with filtering and pagination."""
        query = self._client.table("audit_logs").select("*", count="exact")
        
        if admin_id:
            query = query.eq("admin_id", admin_id)
        if supplier_id:
            query = query.eq("supplier_id", supplier_id)
        if action:
            query = query.eq("action", action)
        
        offset = (page - 1) * page_size
        query = query.order("timestamp", desc=True).range(offset, offset + page_size - 1)
        
        result = query.execute()
        
        total = result.count if result.count else 0
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "items": result.data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    
    # ============== Supplier Activity Operations ==============
    
    async def get_supplier_activity(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """Get supplier activity record."""
        result = self._client.table("supplier_activity").select("*").eq("supplier_id", supplier_id).execute()
        return result.data[0] if result.data else None
    
    async def upsert_supplier_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update supplier activity record."""
        result = self._client.table("supplier_activity").upsert(data).execute()
        return result.data[0] if result.data else None
    
    # ============== Analytics Queries ==============
    
    async def get_status_distribution(self) -> List[Dict[str, Any]]:
        """Get supplier count grouped by status."""
        result = self._client.rpc("get_status_distribution").execute()
        return result.data
    
    async def get_supplier_count_by_category(self) -> List[Dict[str, Any]]:
        """Get supplier count grouped by category."""
        result = self._client.rpc("get_supplier_count_by_category").execute()
        return result.data
    
    async def get_location_stats(self) -> List[Dict[str, Any]]:
        """Get supplier count grouped by city."""
        result = self._client.rpc("get_location_stats").execute()
        return result.data
    
    async def get_location_stats_by_country(self) -> List[Dict[str, Any]]:
        """Get supplier count grouped by country."""
        result = self._client.rpc("get_location_stats_by_country").execute()
        return result.data
    
    async def get_monthly_trends(self, months_back: int = 12) -> List[Dict[str, Any]]:
        """Get monthly registration counts."""
        result = self._client.rpc("get_monthly_trends", {"months_back": months_back}).execute()
        return result.data
    
    async def get_weekly_trends(self, weeks_back: int = 12) -> List[Dict[str, Any]]:
        """Get weekly registration counts."""
        result = self._client.rpc("get_weekly_trends", {"weeks_back": weeks_back}).execute()
        return result.data
    
    async def get_overview_stats(self) -> Dict[str, Any]:
        """Get overview statistics for dashboard."""
        result = self._client.rpc("get_overview_stats").execute()
        return result.data[0] if result.data else {}
    
    # ============== Cleanup Operations ==============
    
    async def cleanup_rejected_applications(self, days: int = 30) -> int:
        """
        Delete rejected applications older than specified days.
        Returns the count of deleted records.
        """
        result = self._client.rpc(
            "cleanup_rejected_applications",
            {"retention_days": days}
        ).execute()
        return result.data if result.data else 0
    
    # ============== Audit Log Operations ==============
    
    async def create_audit_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an audit log entry."""
        result = self._client.table("audit_logs").insert(data).execute()
        return result.data[0] if result.data else None
    
    async def get_audit_logs(
        self,
        admin_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
        user_type: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get audit logs with filtering and pagination.
        
        Returns dict with 'items' and 'total' keys.
        """
        query = self._client.table("audit_logs").select("*", count="exact")
        
        # Apply filters
        if admin_id:
            query = query.eq("admin_id", admin_id)
        if supplier_id:
            query = query.eq("supplier_id", supplier_id)
        if user_type:
            query = query.eq("user_type", user_type)
        if action:
            query = query.eq("action", action)
        if resource_type:
            query = query.eq("resource_type", resource_type)
        if resource_id:
            query = query.eq("resource_id", resource_id)
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date)
        
        # Apply pagination and ordering
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        return {
            "items": result.data if result.data else [],
            "total": result.count if result.count else 0
        }
    
    async def get_resource_audit_trail(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific resource."""
        result = self._client.table("audit_logs")\
            .select("*")\
            .eq("resource_type", resource_type)\
            .eq("resource_id", resource_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data if result.data else []
    
    async def get_recent_activity(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent system activity."""
        # Use the database function if available, otherwise query directly
        try:
            result = self._client.rpc(
                "get_recent_activity",
                {"days_back": days, "limit_count": limit}
            ).execute()
            return result.data if result.data else []
        except:
            # Fallback to direct query
            from datetime import datetime, timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = self._client.table("audit_logs")\
                .select("*")\
                .gte("created_at", cutoff_date)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
    
    async def get_audit_statistics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get audit log statistics."""
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            
            result = self._client.rpc("get_audit_statistics", params).execute()
            return result.data if result.data else []
        except:
            # Fallback to basic stats
            query = self._client.table("audit_logs").select("action", count="exact")
            
            if start_date:
                query = query.gte("created_at", start_date)
            if end_date:
                query = query.lte("created_at", end_date)
            
            result = query.execute()
            
            return {
                "total_actions": result.count if result.count else 0,
                "actions_by_type": {}
            }
    
    # ============================================================
    # Messaging Methods
    # ============================================================
    
    async def create_message_thread(
        self,
        subject: str,
        supplier_id: str,
        category_id: Optional[str],
        priority: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        message_text: str
    ) -> Dict[str, Any]:
        """Create a new message thread with initial message."""
        result = self._client.rpc("create_message_thread", {
            "p_subject": subject,
            "p_supplier_id": supplier_id,
            "p_category_id": category_id,
            "p_priority": priority,
            "p_sender_type": sender_type,
            "p_sender_id": sender_id,
            "p_sender_name": sender_name,
            "p_message_text": message_text
        }).execute()
        
        thread_id = result.data
        
        # Fetch and return the thread details
        return await self.get_thread_by_id(thread_id)
    
    async def add_message_to_thread(
        self,
        thread_id: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        message_text: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Add a message to an existing thread."""
        message_data = {
            "thread_id": thread_id,
            "sender_type": sender_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "message_text": message_text,
            "attachments": attachments or []
        }
        
        result = self._client.table("messages")\
            .insert(message_data)\
            .execute()
        
        return result.data[0] if result.data else None
    
    async def get_thread_by_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get thread details by ID."""
        result = self._client.table("thread_summary")\
            .select("*")\
            .eq("id", thread_id)\
            .single()\
            .execute()
        
        return result.data if result.data else None
    
    async def get_thread_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a thread."""
        result = self._client.table("messages")\
            .select("*")\
            .eq("thread_id", thread_id)\
            .order("created_at", desc=False)\
            .execute()
        
        return result.data if result.data else []
    
    async def get_threads_for_supplier(
        self,
        supplier_id: str,
        is_archived: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get message threads for a supplier with pagination."""
        offset = (page - 1) * page_size
        
        query = self._client.table("thread_summary")\
            .select("*", count="exact")\
            .eq("supplier_id", supplier_id)\
            .order("last_message_at", desc=True)
        
        if is_archived is not None:
            query = query.eq("is_archived", is_archived)
        
        result = query.range(offset, offset + page_size - 1).execute()
        
        return {
            "threads": result.data if result.data else [],
            "total": result.count if result.count else 0,
            "page": page,
            "page_size": page_size
        }
    
    async def get_all_threads(
        self,
        is_archived: Optional[bool] = None,
        category_id: Optional[str] = None,
        priority: Optional[str] = None,
        has_unread: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get all message threads with filters (admin view)."""
        offset = (page - 1) * page_size
        
        query = self._client.table("thread_summary")\
            .select("*", count="exact")\
            .order("last_message_at", desc=True)
        
        if is_archived is not None:
            query = query.eq("is_archived", is_archived)
        if category_id:
            query = query.eq("category_id", category_id)
        if priority:
            query = query.eq("priority", priority)
        if has_unread:
            query = query.gt("unread_by_admin", 0)
        
        result = query.range(offset, offset + page_size - 1).execute()
        
        return {
            "threads": result.data if result.data else [],
            "total": result.count if result.count else 0,
            "page": page,
            "page_size": page_size
        }
    
    async def mark_thread_as_read(
        self,
        thread_id: str,
        user_type: str
    ) -> int:
        """Mark all messages in a thread as read for a user."""
        result = self._client.rpc("mark_messages_as_read", {
            "p_thread_id": thread_id,
            "p_user_type": user_type
        }).execute()
        
        return result.data if result.data is not None else 0
    
    async def get_unread_count(
        self,
        user_id: str,
        user_type: str
    ) -> int:
        """Get total unread message count for a user."""
        result = self._client.rpc("get_total_unread_messages", {
            "p_user_id": user_id,
            "p_user_type": user_type
        }).execute()
        
        return result.data if result.data is not None else 0
    
    async def update_thread(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update thread properties."""
        result = self._client.table("message_threads")\
            .update(updates)\
            .eq("id", thread_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    async def get_message_categories(self) -> List[Dict[str, Any]]:
        """Get all message categories."""
        result = self._client.table("message_categories")\
            .select("*")\
            .order("name")\
            .execute()
        
        return result.data if result.data else []
    
    # ============================================================
    # Timeline Methods
    # ============================================================
    
    async def get_supplier_timeline(
        self,
        supplier_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get complete timeline for a supplier."""
        result = self._client.rpc("get_supplier_timeline", {
            "p_supplier_id": supplier_id,
            "p_limit": limit
        }).execute()
        
        return result.data if result.data else []
    
    async def get_supplier_status_history(
        self,
        supplier_id: str
    ) -> List[Dict[str, Any]]:
        """Get status change history for a supplier."""
        result = self._client.rpc("get_supplier_status_history", {
            "p_supplier_id": supplier_id
        }).execute()
        
        return result.data if result.data else []
    
    async def log_supplier_activity(
        self,
        supplier_id: str,
        activity_type: str,
        activity_title: str,
        activity_description: str = None,
        actor_type: str = "system",
        actor_id: str = None,
        actor_name: str = "System",
        metadata: Dict[str, Any] = None
    ) -> str:
        """Log a supplier activity."""
        result = self._client.rpc("log_supplier_activity", {
            "p_supplier_id": supplier_id,
            "p_activity_type": activity_type,
            "p_activity_title": activity_title,
            "p_activity_description": activity_description,
            "p_actor_type": actor_type,
            "p_actor_id": actor_id,
            "p_actor_name": actor_name,
            "p_metadata": metadata or {}
        }).execute()
        
        return result.data if result.data else None


# Singleton instance
db = Database()


def get_db() -> Database:
    """Get database instance (for dependency injection)."""
    return db
