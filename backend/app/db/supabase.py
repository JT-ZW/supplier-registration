"""
Supabase database client and utilities.
"""

import asyncio
from datetime import datetime, timedelta, date
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
    
    @staticmethod
    def _derive_esg_booleans_from_counts(row: Dict[str, Any]) -> tuple[bool, bool]:
        """Derive ESG ownership flags from key-person counts using >50% thresholds."""
        total_key_persons = row.get("key_person_count") or 0
        female_count = row.get("female_director_count") or 0
        youth_count = row.get("youth_director_count") or 0
    
        if total_key_persons <= 0:
            return False, False
    
        return (female_count / total_key_persons) > 0.5, (youth_count / total_key_persons) > 0.5
    
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
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "submitted_at",
        ascending: bool = False
    ) -> Dict[str, Any]:
        """List suppliers with advanced filtering and pagination."""
        query = self._client.table("suppliers").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        if category:
            # Use supplier_categories table to support multi-category filtering
            cat_ids_result = self._client.table("supplier_categories").select("supplier_id").eq("category", category).execute()
            cat_ids = [r["supplier_id"] for r in (cat_ids_result.data or [])]
            if cat_ids:
                query = query.in_("id", cat_ids)
            else:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

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
        if date_from:
            query = query.gte("submitted_at", date_from)
        if date_to:
            try:
                end_of_day = (
                    datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, microsecond=999999)
                )
                query = query.lte("submitted_at", end_of_day.isoformat())
            except ValueError:
                query = query.lte("submitted_at", date_to)
        
        # General search (legacy support)
        if search:
            query = query.or_(f"company_name.ilike.%{search}%,email.ilike.%{search}%,contact_person_name.ilike.%{search}%")
        
        # Pagination
        offset = (page - 1) * page_size
        # Validate order_by to prevent injection — whitelist allowed columns
        allowed_sort_columns = {
            "company_name", "business_category", "status",
            "created_at", "submitted_at", "updated_at",
        }
        if order_by not in allowed_sort_columns:
            order_by = "submitted_at"
        query = query.order(order_by, desc=not ascending, nullsfirst=False)
        if order_by == "submitted_at":
            query = query.order("created_at", desc=True)
        # Secondary sort: when sorting by category, always sort company name A→Z within each category
        if order_by == "business_category":
            query = query.order("company_name", desc=False)
        query = query.range(offset, offset + page_size - 1)
        
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

    async def get_sustainability_doc_submissions(
        self,
        supplier_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all sustainability/QC document submissions.

        Returns rows from the documents table where document_type is one of the
        recognised sustainability types, optionally filtered to a specific list
        of supplier IDs (e.g. those already filtered for a report).
        """
        from ..models.enums import SUSTAINABILITY_DOC_TYPES

        doc_type_values = [dt.value for dt in SUSTAINABILITY_DOC_TYPES]

        query = (
            self._client.table("documents")
            .select("supplier_id, document_type, verification_status, uploaded_at")
            .in_("document_type", doc_type_values)
        )

        if supplier_ids:
            query = query.in_("supplier_id", supplier_ids)

        result = query.execute()
        return result.data if result.data else []

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
            .eq("is_active", "true")\
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
            # Filter by target_id (the canonical field for supplier/vendor ID)
            query = query.eq("target_id", supplier_id)
        if action:
            query = query.eq("action", action)
        
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)
        
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
        """Get supplier count grouped by category using supplier_categories table (multi-category aware)."""
        cats_result = self._client.table("supplier_categories").select("supplier_id, category").execute()
        cat_rows = cats_result.data or []
        if not cat_rows:
            return []

        supplier_ids = list({r["supplier_id"] for r in cat_rows})
        sup_result = self._client.table("suppliers").select("id, status").in_("id", supplier_ids).execute()
        status_map = {s["id"]: s["status"] for s in (sup_result.data or [])}

        category_map: Dict[str, Dict[str, Any]] = {}
        for row in cat_rows:
            cat = row["category"]
            sup_status = status_map.get(row["supplier_id"], "")
            if cat not in category_map:
                category_map[cat] = {
                    "category": cat,
                    "total_count": 0,
                    "approved_count": 0,
                    "pending_count": 0,
                    "rejected_count": 0,
                }
            category_map[cat]["total_count"] += 1
            if sup_status == "APPROVED":
                category_map[cat]["approved_count"] += 1
            elif sup_status in ("SUBMITTED", "INCOMPLETE", "UNDER_REVIEW", "NEED_MORE_INFO"):
                category_map[cat]["pending_count"] += 1
            elif sup_status == "REJECTED":
                category_map[cat]["rejected_count"] += 1

        return sorted(category_map.values(), key=lambda x: x["total_count"], reverse=True)
    
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

    # ============== Key Persons Operations ==============

    async def create_key_person(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a key person record for a supplier."""
        result = self._client.table("supplier_key_persons").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_key_persons_by_supplier(self, supplier_id: str) -> List[Dict[str, Any]]:
        """Get all key persons for a supplier."""
        result = (
            self._client.table("supplier_key_persons")
            .select("*")
            .eq("supplier_id", supplier_id)
            .order("created_at")
            .execute()
        )
        return result.data if result.data else []

    async def delete_key_person(self, key_person_id: str) -> bool:
        """Delete a key person record."""
        self._client.table("supplier_key_persons").delete().eq("id", key_person_id).execute()
        return True

    async def delete_key_persons_by_supplier(self, supplier_id: str) -> bool:
        """Delete all key persons for a supplier."""
        self._client.table("supplier_key_persons").delete().eq("supplier_id", supplier_id).execute()
        return True

    # ============== Trade References Operations ==============

    async def create_trade_reference(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a trade reference record for a supplier."""
        result = self._client.table("supplier_trade_references").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_trade_references_by_supplier(self, supplier_id: str) -> List[Dict[str, Any]]:
        """Get all trade references for a supplier."""
        result = (
            self._client.table("supplier_trade_references")
            .select("*")
            .eq("supplier_id", supplier_id)
            .order("created_at")
            .execute()
        )
        return result.data if result.data else []

    async def delete_trade_references_by_supplier(self, supplier_id: str) -> bool:
        """Delete all trade references for a supplier."""
        self._client.table("supplier_trade_references").delete().eq("supplier_id", supplier_id).execute()
        return True

    # ============== Supplier Categories Operations ==============

    async def create_supplier_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a category for a supplier."""
        result = self._client.table("supplier_categories").insert(data).execute()
        return result.data[0] if result.data else None

    async def get_supplier_categories(self, supplier_id: str) -> List[Dict[str, Any]]:
        """Get all categories for a supplier."""
        result = (
            self._client.table("supplier_categories")
            .select("*")
            .eq("supplier_id", supplier_id)
            .order("created_at")
            .execute()
        )
        return result.data if result.data else []

    async def get_supplier_category_access_summary(self, supplier_id: str) -> Dict[str, Any]:
        """Return allowed/blocked category participation based on current compliance evidence."""
        from ..models.enums import (
            DocumentType,
            EXPIRY_REQUIRED_DOCUMENT_TYPES,
            get_statutory_documents,
            get_supplier_type,
        )

        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return {
                "supplier_id": supplier_id,
                "category_count": 0,
                "allowed_categories": [],
                "blocked_categories": [],
                "excluded_categories": [],
                "mandatory_met_categories": 0,
                "mandatory_missing_categories": 0,
                "non_excluded_categories": 0,
                "mandatory_statutory_met": False,
                "mandatory_statutory_has_expired": False,
            }

        documents = await self.get_documents_by_supplier(supplier_id)
        today = date.today()
        expiry_required_types = set(EXPIRY_REQUIRED_DOCUMENT_TYPES)

        valid_verified_doc_types: set[DocumentType] = set()
        for doc in documents:
            if doc.get("verification_status") != "VERIFIED":
                continue
            if doc.get("is_archived") is True:
                continue

            raw_type = doc.get("document_type")
            try:
                doc_type = DocumentType(raw_type)
            except Exception:
                continue

            if doc_type in expiry_required_types:
                expiry_value = doc.get("expiry_date")
                if not expiry_value:
                    continue

                expiry_date_value: Optional[date] = None
                if isinstance(expiry_value, date):
                    expiry_date_value = expiry_value
                elif isinstance(expiry_value, str):
                    try:
                        expiry_date_value = date.fromisoformat(expiry_value[:10])
                    except ValueError:
                        continue

                if not expiry_date_value or expiry_date_value < today:
                    continue

            valid_verified_doc_types.add(doc_type)

        supplier_type = get_supplier_type(
            supplier.get("country", ""),
            bool(supplier.get("is_small_scale_farmer", False)),
        )
        statutory_docs = get_statutory_documents(supplier_type)
        mandatory_statutory_met = all(doc_type in valid_verified_doc_types for doc_type in statutory_docs)

        # Check whether any statutory doc is *actually expired* (vs. just unverified/pending).
        # Suspension is only warranted for expired docs; missing/unverified → COMPLIANCE_REQUIRED.
        mandatory_statutory_has_expired = False
        statutory_doc_set = set(statutory_docs)
        for doc in documents:
            if doc.get("is_archived") is True:
                continue
            raw_type = doc.get("document_type")
            try:
                doc_type = DocumentType(raw_type)
            except Exception:
                continue
            if doc_type not in statutory_doc_set:
                continue
            # Already flagged as EXPIRED by the daily expiry flag job
            if doc.get("verification_status") == "EXPIRED":
                mandatory_statutory_has_expired = True
                break
            # Verified doc whose expiry date has passed (belt-and-suspenders check)
            if doc.get("verification_status") == "VERIFIED" and doc_type in expiry_required_types:
                _exp_value = doc.get("expiry_date")
                if _exp_value:
                    _exp_date = None
                    if isinstance(_exp_value, date):
                        _exp_date = _exp_value
                    elif isinstance(_exp_value, str):
                        try:
                            _exp_date = date.fromisoformat(_exp_value[:10])
                        except ValueError:
                            pass
                    if _exp_date and _exp_date < today:
                        mandatory_statutory_has_expired = True
                        break

        categories = await self.get_supplier_categories(supplier_id)
        allowed_categories: List[str] = []
        blocked_categories: List[str] = []
        excluded_categories: List[str] = []

        for row in categories:
            category_name = row.get("category")
            compliance_status = (row.get("compliance_status") or "PENDING").upper()
            if not category_name:
                continue

            if compliance_status == "EXCLUDED":
                excluded_categories.append(category_name)
            elif compliance_status in ("FULL_COMPLIANCE", "MEDIUM_RISK"):
                allowed_categories.append(category_name)
            else:
                blocked_categories.append(category_name)

        allowed_categories = sorted(allowed_categories)
        blocked_categories = sorted(blocked_categories)
        excluded_categories = sorted(excluded_categories)

        category_count = len(categories)
        non_excluded_categories = max(0, category_count - len(excluded_categories))

        return {
            "supplier_id": supplier_id,
            "category_count": category_count,
            "allowed_categories": allowed_categories,
            "blocked_categories": blocked_categories,
            "excluded_categories": excluded_categories,
            "mandatory_met_categories": len(allowed_categories),
            "mandatory_missing_categories": len(blocked_categories),
            "non_excluded_categories": non_excluded_categories,
            "mandatory_statutory_met": mandatory_statutory_met,
            "mandatory_statutory_has_expired": mandatory_statutory_has_expired,
        }

    async def delete_supplier_category(self, supplier_id: str, category: str) -> bool:
        """Remove a category from a supplier."""
        self._client.table("supplier_categories").delete().eq("supplier_id", supplier_id).eq("category", category).execute()
        return True

    async def delete_supplier_categories(self, supplier_id: str) -> bool:
        """Delete all categories for a supplier."""
        self._client.table("supplier_categories").delete().eq("supplier_id", supplier_id).execute()
        return True

    async def update_supplier_category_compliance(
        self,
        supplier_id: str,
        category: str,
        compliance_status: str,
    ) -> Optional[Dict[str, Any]]:
        """Update compliance status for a supplier's category."""
        from datetime import datetime, timezone
        result = (
            self._client.table("supplier_categories")
            .update({"compliance_status": compliance_status, "compliance_checked_at": datetime.now(timezone.utc).isoformat()})
            .eq("supplier_id", supplier_id)
            .eq("category", category)
            .execute()
        )
        return result.data[0] if result.data else None

    async def recompute_supplier_category_compliance(self, supplier_id: str) -> List[Dict[str, Any]]:
        """Recompute and persist compliance status for all categories of one supplier.

        Uses only VERIFIED, non-archived and non-expired documents as evidence.
        """
        from ..models.enums import (
            BusinessCategory,
            CERT_GROUPS_BY_CATEGORY,
            ComplianceLevel,
            DocumentType,
            EXPIRY_REQUIRED_DOCUMENT_TYPES,
            get_statutory_documents,
            get_supplier_type,
        )

        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return []

        categories = await self.get_supplier_categories(supplier_id)
        if not categories:
            return []

        documents = await self.get_documents_by_supplier(supplier_id)
        expiry_required_types = set(EXPIRY_REQUIRED_DOCUMENT_TYPES)
        today = date.today()

        verified_doc_types: set[DocumentType] = set()
        for doc in documents:
            if doc.get("verification_status") != "VERIFIED":
                continue
            if doc.get("is_archived") is True:
                continue
            raw_type = doc.get("document_type")
            try:
                doc_type = DocumentType(raw_type)
            except Exception:
                continue

            # Expiry-tracked documents stop contributing to compliance once expired.
            if doc_type in expiry_required_types:
                expiry_value = doc.get("expiry_date")
                if not expiry_value:
                    continue

                expiry_date_value: Optional[date] = None
                if isinstance(expiry_value, date):
                    expiry_date_value = expiry_value
                elif isinstance(expiry_value, str):
                    try:
                        expiry_date_value = date.fromisoformat(expiry_value[:10])
                    except ValueError:
                        continue

                if not expiry_date_value or expiry_date_value < today:
                    continue

            verified_doc_types.add(doc_type)

        supplier_type = get_supplier_type(
            supplier.get("country", ""),
            bool(supplier.get("is_small_scale_farmer", False)),
        )
        statutory_docs = get_statutory_documents(supplier_type)
        mandatory_statutory_met = all(doc_type in verified_doc_types for doc_type in statutory_docs)

        updated_rows: List[Dict[str, Any]] = []
        for cat_row in categories:
            cat_value = cat_row.get("category")
            try:
                category_enum = BusinessCategory(cat_value)
                if not mandatory_statutory_met:
                    compliance_status = ComplianceLevel.HIGH_RISK.value
                else:
                    groups = CERT_GROUPS_BY_CATEGORY.get(category_enum, [])
                    if not groups:
                        # Categories without explicit cert groups still require statutory docs.
                        compliance_status = ComplianceLevel.FULL_COMPLIANCE.value
                    else:
                        mandatory_group_missing = False
                        preferred_group_missing = False
                        for group in groups:
                            group_satisfied = any(doc_type in verified_doc_types for doc_type in group.document_types)
                            if group_satisfied:
                                continue
                            if group.is_mandatory_upload:
                                mandatory_group_missing = True
                            elif group.requirement_level != "FUTURE_SUSTAINABILITY":
                                preferred_group_missing = True

                        if mandatory_group_missing:
                            compliance_status = ComplianceLevel.HIGH_RISK.value
                        elif preferred_group_missing:
                            compliance_status = ComplianceLevel.MEDIUM_RISK.value
                        else:
                            compliance_status = ComplianceLevel.FULL_COMPLIANCE.value
            except Exception:
                compliance_status = ComplianceLevel.EXCLUDED.value

            updated = await self.update_supplier_category_compliance(
                supplier_id=supplier_id,
                category=cat_value,
                compliance_status=compliance_status,
            )
            if updated:
                updated_rows.append(updated)

        return updated_rows

    async def recompute_supplier_portfolio_status(self, supplier_id: str) -> Dict[str, Any]:
        """Recompute supplier-level status from statutory compliance outcomes only.

        Policy:
        - Expired statutory mandatory documents -> SUSPENDED.
        - Statutory mandatory docs missing or unverified (not expired) -> COMPLIANCE_REQUIRED.
        - Statutory requirements met -> APPROVED (regardless of category-doc status).

        Category-level doc issues (expired or missing category docs) are tracked in
        supplier_categories.compliance_status and surfaced as compliance flags, but they
        do NOT demote a supplier from APPROVED. Only statutory doc expiry triggers suspension.
        """
        from ..models.enums import SupplierStatus

        supplier = await self.get_supplier_by_id(supplier_id)
        if not supplier:
            return {"changed": False, "reason": "supplier_not_found"}

        current_status = supplier.get("status") or ""
        managed_statuses = {
            SupplierStatus.APPROVED.value,
            SupplierStatus.COMPLIANCE_REQUIRED.value,
            SupplierStatus.SUSPENDED.value,
        }
        if current_status not in managed_statuses:
            return {
                "changed": False,
                "supplier_id": supplier_id,
                "previous_status": current_status,
                "new_status": current_status,
                "reason": "status_not_managed",
            }

        access_summary = await self.get_supplier_category_access_summary(supplier_id)
        mandatory_statutory_met = bool(access_summary.get("mandatory_statutory_met"))
        mandatory_statutory_has_expired = bool(access_summary.get("mandatory_statutory_has_expired"))
        categories = await self.get_supplier_categories(supplier_id)
        mandatory_met_count = int(access_summary.get("mandatory_met_categories", 0) or 0)
        mandatory_missing_count = int(access_summary.get("mandatory_missing_categories", 0) or 0)
        non_excluded_total = int(access_summary.get("non_excluded_categories", 0) or 0)
        allowed_categories = list(access_summary.get("allowed_categories") or [])
        blocked_categories = list(access_summary.get("blocked_categories") or [])

        new_status = current_status
        reason = "no_change"
        if not mandatory_statutory_met:
            if mandatory_statutory_has_expired:
                # One or more statutory docs have expired — suspend regardless of current status
                new_status = SupplierStatus.SUSPENDED.value
                reason = "statutory_documents_expired"
            elif current_status == SupplierStatus.APPROVED.value:
                # Docs are missing/unverified but the admin already explicitly approved this
                # supplier. Do NOT downgrade — only expiry can touch an APPROVED supplier.
                new_status = SupplierStatus.APPROVED.value
                reason = "no_change_approved_statutory_unverified"
            else:
                # Supplier is already COMPLIANCE_REQUIRED or SUSPENDED with no expired docs —
                # keep at COMPLIANCE_REQUIRED so they know docs are needed.
                new_status = SupplierStatus.COMPLIANCE_REQUIRED.value
                reason = "statutory_mandatory_missing_or_unverified"
        else:
            # All statutory requirements are satisfied → APPROVED.
            # Category-level doc issues are tracked per-category and surfaced as compliance
            # flags only; they never remove a supplier from the approved list.
            new_status = SupplierStatus.APPROVED.value
            reason = "statutory_requirements_met"

        changed = new_status != current_status

        if changed:
            update_data: Dict[str, Any] = {
                "status": new_status,
                "updated_at": datetime.utcnow().isoformat(),
            }

            if new_status == SupplierStatus.SUSPENDED.value:
                update_data["suspended_at"] = supplier.get("suspended_at") or datetime.utcnow().isoformat()
                update_data["suspension_reason"] = (
                    "Supplier is suspended because one or more statutory mandatory "
                    "documents have expired."
                )
                if "suspension_triggered_by" in supplier:
                    update_data["suspension_triggered_by"] = "SYSTEM"
            else:
                update_data["suspended_at"] = None
                update_data["suspension_reason"] = None
                if "suspension_triggered_by" in supplier:
                    update_data["suspension_triggered_by"] = None

            await self.update_supplier(supplier_id, update_data)

        return {
            "changed": changed,
            "supplier_id": supplier_id,
            "previous_status": current_status,
            "new_status": new_status,
            "reason": reason,
            "category_count": len(categories),
            "mandatory_met_categories": mandatory_met_count,
            "mandatory_missing_categories": mandatory_missing_count,
            "non_excluded_categories": non_excluded_total,
            "mandatory_statutory_met": mandatory_statutory_met,
            "allowed_categories": allowed_categories,
            "blocked_categories": blocked_categories,
        }

    async def recompute_category_compliance_for_suppliers(
        self,
        statuses: Optional[List[str]] = None,
    ) -> int:
        """Recompute category compliance for all suppliers, optionally filtered by status."""
        query = self._client.table("suppliers").select("id")
        if statuses:
            query = query.in_("status", statuses)

        result = query.execute()
        suppliers = result.data or []

        # Process suppliers in parallel (capped at 8 concurrent workers) instead of
        # the previous sequential-await loop that caused one DB round-trip per supplier.
        semaphore = asyncio.Semaphore(8)

        async def _recompute_one(supplier_id: str) -> bool:
            async with semaphore:
                try:
                    await self.recompute_supplier_category_compliance(supplier_id)
                    # recompute_supplier_portfolio_status is intentionally NOT called here.
                    # Only the daily expiry job (expiry_service.py) may trigger supplier
                    # status changes. This function only updates supplier_categories rows,
                    # never suppliers.status.
                    return True
                except Exception:
                    return False

        results = await asyncio.gather(
            *[_recompute_one(s["id"]) for s in suppliers if s.get("id")],
            return_exceptions=False,
        )
        return sum(1 for ok in results if ok)

    async def recompute_portfolio_status_for_suppliers(
        self,
        statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Recompute supplier-level portfolio status for a set of suppliers."""
        query = self._client.table("suppliers").select("id")
        if statuses:
            query = query.in_("status", statuses)

        result = query.execute()
        suppliers = result.data or []

        transitions: List[Dict[str, Any]] = []
        for supplier in suppliers:
            supplier_id = supplier.get("id")
            if not supplier_id:
                continue
            try:
                transition = await self.recompute_supplier_portfolio_status(supplier_id)
                transitions.append(transition)
            except Exception:
                continue

        return transitions

    async def backfill_supplier_categories_from_primary(
        self,
        statuses: Optional[List[str]] = None,
    ) -> int:
        """Backfill missing supplier_categories rows from suppliers.business_category.

        This is a safety net for legacy rows created before multi-category support
        or for records where category rows were not persisted correctly.
        """
        supplier_query = self._client.table("suppliers").select("id,business_category")
        if statuses:
            supplier_query = supplier_query.in_("status", statuses)

        supplier_result = supplier_query.execute()
        suppliers = supplier_result.data or []
        if not suppliers:
            return 0

        supplier_ids = [s.get("id") for s in suppliers if s.get("id")]
        if not supplier_ids:
            return 0

        categories_result = (
            self._client.table("supplier_categories")
            .select("supplier_id,category")
            .in_("supplier_id", supplier_ids)
            .execute()
        )
        category_rows = categories_result.data or []

        supplier_to_categories: Dict[str, set[str]] = {}
        for row in category_rows:
            sid = row.get("supplier_id")
            cat = row.get("category")
            if not sid or not cat:
                continue
            supplier_to_categories.setdefault(sid, set()).add(cat)

        inserts: List[Dict[str, Any]] = []
        for supplier in suppliers:
            sid = supplier.get("id")
            primary_category = supplier.get("business_category")
            if not sid or not primary_category:
                continue

            existing_categories = supplier_to_categories.get(sid, set())
            if primary_category not in existing_categories:
                inserts.append(
                    {
                        "supplier_id": sid,
                        "category": primary_category,
                        "compliance_status": "PENDING",
                    }
                )

        if not inserts:
            return 0

        # ON CONFLICT keeps this operation idempotent.
        self._client.table("supplier_categories").upsert(
            inserts,
            on_conflict="supplier_id,category",
        ).execute()

        return len(inserts)

    # ============== Farmer Application Form Operations ==============

    async def create_farmer_form(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or replace the farmer application form for a supplier."""
        result = (
            self._client.table("farmer_application_forms")
            .upsert(data, on_conflict="supplier_id")
            .execute()
        )
        return result.data[0] if result.data else None

    async def get_farmer_form(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """Get the farmer application form for a supplier."""
        result = (
            self._client.table("farmer_application_forms")
            .select("*")
            .eq("supplier_id", supplier_id)
            .execute()
        )
        return result.data[0] if result.data else None

    async def delete_farmer_form(self, supplier_id: str) -> bool:
        """Delete the farmer application form for a supplier."""
        self._client.table("farmer_application_forms").delete().eq("supplier_id", supplier_id).execute()
        return True

    # ============== Sustainability / ESG View Queries ==============

    async def get_esg_summary(
        self,
        country: Optional[str] = None,
        supplier_type: Optional[str] = None,
        business_size: Optional[str] = None,
        status: Optional[str] = None,
        columns: str = "*",
    ) -> List[Dict[str, Any]]:
        """Query vw_esg_supplier_summary with optional filters."""
        query = self._client.table("vw_esg_supplier_summary").select(columns)
        if country:
            query = query.ilike("country", f"%{country}%")
        if business_size:
            query = query.eq("business_size", business_size)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        rows = result.data or []
        # supplier_type is derived in Python (not a DB column on the view)
        if supplier_type:
            rows = [r for r in rows if r.get("supplier_type") == supplier_type]
        return rows

    async def get_category_compliance_stats(
        self,
        country: Optional[str] = None,
        business_size: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return category compliance matrix with full category coverage and mandatory summary."""
        from ..models.enums import BusinessCategory

        # When no explicit status filter is given, scope to approved/active suppliers only.
        # UNDER_REVIEW / SUBMITTED suppliers have no verified docs yet so they
        # distort the compliance percentages on the sustainability dashboard.
        ACTIVE_SCOPE = ["APPROVED", "COMPLIANCE_REQUIRED", "SUSPENDED"]

        supplier_query = self._client.table("suppliers").select("id,business_category")
        if status:
            supplier_query = supplier_query.eq("status", status)
        else:
            supplier_query = supplier_query.in_("status", ACTIVE_SCOPE)
        if country:
            supplier_query = supplier_query.ilike("country", f"%{country}%")
        if business_size:
            supplier_query = supplier_query.eq("business_size", business_size)

        suppliers_result = supplier_query.execute()
        suppliers = suppliers_result.data or []
        supplier_ids = [row.get("id") for row in suppliers if row.get("id")]

        # Include every category configured in the enum so empty categories are visible.
        all_category_names = {category.value for category in BusinessCategory}
        all_category_names.update(
            row.get("business_category")
            for row in suppliers
            if row.get("business_category")
        )

        if not supplier_ids:
            return [
                {
                    "category": category,
                    "total_suppliers": 0,
                    "full_compliance_count": 0,
                    "medium_risk_count": 0,
                    "high_risk_count": 0,
                    "pending_count": 0,
                    "excluded_count": 0,
                    "mandatory_met_count": 0,
                    "mandatory_missing_count": 0,
                    "full_compliance_pct": 0.0,
                }
                for category in sorted(all_category_names)
            ]

        category_rows_result = (
            self._client.table("supplier_categories")
            .select("supplier_id,category,compliance_status")
            .in_("supplier_id", supplier_ids)
            .execute()
        )
        category_rows = category_rows_result.data or []

        stats: Dict[str, Dict[str, Any]] = {
            category: {
                "category": category,
                "total_suppliers": 0,
                "full_compliance_count": 0,
                "medium_risk_count": 0,
                "high_risk_count": 0,
                "pending_count": 0,
                "excluded_count": 0,
                "mandatory_met_count": 0,
                "mandatory_missing_count": 0,
                "full_compliance_pct": 0.0,
            }
            for category in all_category_names
        }

        for row in category_rows:
            category = row.get("category")
            if not category:
                continue

            if category not in stats:
                stats[category] = {
                    "category": category,
                    "total_suppliers": 0,
                    "full_compliance_count": 0,
                    "medium_risk_count": 0,
                    "high_risk_count": 0,
                    "pending_count": 0,
                    "excluded_count": 0,
                    "mandatory_met_count": 0,
                    "mandatory_missing_count": 0,
                    "full_compliance_pct": 0.0,
                }

            status_value = (row.get("compliance_status") or "PENDING").upper()
            bucket = stats[category]
            bucket["total_suppliers"] += 1

            if status_value == "FULL_COMPLIANCE":
                bucket["full_compliance_count"] += 1
                bucket["mandatory_met_count"] += 1
            elif status_value == "MEDIUM_RISK":
                bucket["medium_risk_count"] += 1
                bucket["mandatory_met_count"] += 1
            elif status_value == "HIGH_RISK":
                bucket["high_risk_count"] += 1
                bucket["mandatory_missing_count"] += 1
            elif status_value == "EXCLUDED":
                bucket["excluded_count"] += 1
            else:
                bucket["pending_count"] += 1
                bucket["mandatory_missing_count"] += 1

        output: List[Dict[str, Any]] = []
        for category in sorted(stats.keys()):
            row = stats[category]
            denominator = row["total_suppliers"] - row["excluded_count"]
            row["full_compliance_pct"] = round(
                (row["full_compliance_count"] / denominator * 100), 1
            ) if denominator > 0 else 0.0
            output.append(row)

        return output

    async def get_business_size_distribution(self) -> List[Dict[str, Any]]:
        """Query vw_business_size_distribution."""
        result = self._client.table("vw_business_size_distribution").select("*").execute()
        return result.data or []

    async def get_document_type_stats(self) -> List[Dict[str, Any]]:
        """Query vw_document_type_stats."""
        result = self._client.table("vw_document_type_stats").select("*").execute()
        return result.data or []

    async def get_sustainability_supplier_list(
        self,
        country: Optional[str] = None,
        business_size: Optional[str] = None,
        status: Optional[str] = None,
        esg_women_owned: Optional[bool] = None,
        esg_youth_owned: Optional[bool] = None,
        is_small_scale_farmer: Optional[bool] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return a filtered supplier list for sustainability exports.

        Notes:
        - supplier_type is NOT a DB column — it is derived in Python from
          is_small_scale_farmer + country.
        - esg_women_owned / esg_youth_owned are derived from key-person counts
          to keep values accurate even if supplier-level cached booleans are stale.
        """
        query = self._client.table("vw_esg_supplier_summary").select("*")
        if country:
            query = query.ilike("country", f"%{country}%")
        if business_size:
            query = query.eq("business_size", business_size)
        if status:
            query = query.eq("status", status)
        if is_small_scale_farmer is not None:
            query = query.eq("is_small_scale_farmer", str(is_small_scale_farmer).lower())

        result = query.execute()
        rows = result.data or []
        if not status:
            approved_scope = {"APPROVED", "COMPLIANCE_REQUIRED", "SUSPENDED"}
            rows = [r for r in rows if (r.get("status") or "") in approved_scope]
        if not rows:
            return []

        supplier_ids = [r.get("id") for r in rows if r.get("id")]
        details_map: Dict[str, Dict[str, Any]] = {}
        if supplier_ids:
            details_result = (
                self._client.table("suppliers")
                .select("id,business_category,years_in_business,created_at")
                .in_("id", supplier_ids)
                .execute()
            )
            details_rows = details_result.data or []
            details_map = {d["id"]: d for d in details_rows if d.get("id")}

        normalized: List[Dict[str, Any]] = []
        for row in rows:
            women_owned_derived, youth_owned_derived = self._derive_esg_booleans_from_counts(row)

            if esg_women_owned is not None and women_owned_derived != esg_women_owned:
                continue
            if esg_youth_owned is not None and youth_owned_derived != esg_youth_owned:
                continue

            supplier_id = row.get("id")
            details = details_map.get(supplier_id, {})
            # business_category is a single value in the DB; wrap in list for API consistency
            raw_category = details.get("business_category")
            business_categories = [raw_category] if raw_category else []
            normalized_row = {
                "id": supplier_id,
                "company_name": row.get("company_name"),
                "country": row.get("country"),
                "status": row.get("status"),
                "business_size": row.get("business_size"),
                "employee_count": row.get("employee_count"),
                "is_small_scale_farmer": row.get("is_small_scale_farmer"),
                "esg_women_owned": women_owned_derived,
                "esg_youth_owned": youth_owned_derived,
                "business_categories": business_categories,
                "years_in_business": details.get("years_in_business"),
                "created_at": details.get("created_at"),
            }

            if normalized_row.get("is_small_scale_farmer"):
                normalized_row["supplier_type"] = "LOCAL_FARMER"
            elif (normalized_row.get("country") or "").strip().lower() in ("zimbabwe", "zw"):
                normalized_row["supplier_type"] = "LOCAL"
            else:
                normalized_row["supplier_type"] = "FOREIGN"

            normalized.append(normalized_row)

        return normalized[:limit]


# Singleton instance
db = Database()


def get_db() -> Database:
    """Get database instance (for dependency injection)."""
    return db
