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
        result = self._client.table("suppliers").update(data).eq("id", supplier_id).execute()
        return result.data[0] if result.data else None
    
    async def delete_supplier(self, supplier_id: str) -> bool:
        """Delete a supplier record."""
        result = self._client.table("suppliers").delete().eq("id", supplier_id).execute()
        return len(result.data) > 0 if result.data else False
    
    async def list_suppliers(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "created_at",
        ascending: bool = False
    ) -> Dict[str, Any]:
        """List suppliers with filtering and pagination."""
        query = self._client.table("suppliers").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        if category:
            query = query.eq("category", category)
        if search:
            query = query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%")
        
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
        """Get supplier count grouped by location."""
        result = self._client.rpc("get_location_stats").execute()
        return result.data
    
    async def get_monthly_trends(self, months_back: int = 12) -> List[Dict[str, Any]]:
        """Get monthly registration counts."""
        result = self._client.rpc("get_monthly_trends", {"months_back": months_back}).execute()
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


# Singleton instance
db = Database()


def get_db() -> Database:
    """Get database instance (for dependency injection)."""
    return db
