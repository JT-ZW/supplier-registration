"""
Supabase Storage utilities for document uploads and downloads.
"""

import uuid
import httpx
from datetime import datetime
from typing import Optional, Dict, Any

from .config import settings


class StorageService:
    """
    Service for interacting with Supabase Storage.
    Handles file uploads, downloads, and URL generation.
    """
    
    def __init__(self):
        """Initialize storage service with Supabase client."""
        self._bucket_name = "supplier-documents"
    
    def _generate_file_path(
        self,
        supplier_id: str,
        document_type: str,
        filename: str
    ) -> str:
        """
        Generate a unique file path for storage.
        
        Format: suppliers/{supplier_id}/{document_type}/{timestamp}_{uuid}_{filename}
        
        Args:
            supplier_id: Supplier's unique identifier
            document_type: Type of document being uploaded
            filename: Original filename
            
        Returns:
            Unique file path string
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        
        return f"suppliers/{supplier_id}/{document_type}/{timestamp}_{unique_id}_{safe_filename}"
    
    def generate_presigned_upload_url(
        self,
        supplier_id: str,
        document_type: str,
        filename: str,
        content_type: str,
        file_size: int
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL for uploading a file to Supabase Storage.
        
        Args:
            supplier_id: Supplier's unique identifier
            document_type: Type of document being uploaded
            filename: Original filename
            content_type: MIME type of the file
            file_size: Size of the file in bytes
            
        Returns:
            Dictionary containing upload URL, file path, and expiration info
            
        Raises:
            ValueError: If file size exceeds maximum allowed or invalid content type
        """
        # Validate file size
        if file_size > settings.max_file_size_bytes:
            raise ValueError(
                f"File size {file_size} bytes exceeds maximum allowed "
                f"{settings.MAX_FILE_SIZE_MB} MB"
            )
        
        # Validate content type
        if content_type not in settings.allowed_file_types_list:
            raise ValueError(
                f"Content type {content_type} is not allowed. "
                f"Allowed types: {', '.join(settings.allowed_file_types_list)}"
            )
        
        file_path = self._generate_file_path(supplier_id, document_type, filename)
        
        try:
            # Generate presigned upload URL using Supabase Storage API
            print(f"🔍 Generating upload URL for path: {file_path}")
            print(f"   Bucket: {self._bucket_name}")
            
            # Create signed upload URL directly
            url = f"{settings.SUPABASE_URL}/storage/v1/object/upload/sign/{self._bucket_name}/{file_path}"
            
            response = httpx.post(
                url,
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                },
                timeout=30.0
            )
            
            print(f"📦 Supabase response status: {response.status_code}")
            print(f"📦 Supabase response: {response.text}")
            
            if response.status_code not in [200, 201]:
                raise ValueError(f"Failed to generate signed URL: {response.text}")
            
            signed_data = response.json()
            upload_url = signed_data.get("url") or signed_data.get("signedURL")
            
            if not upload_url:
                raise ValueError(f"No upload URL in response: {signed_data}")
            
            # Make the URL absolute if it's relative
            if upload_url.startswith("/"):
                upload_url = f"{settings.SUPABASE_URL}/storage/v1{upload_url}"
            
            return {
                "upload_url": upload_url,
                "file_path": file_path,
                "token": signed_data.get("token"),
                "expires_in": 3600  # Supabase signed URLs expire in 1 hour
            }
            
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {str(e)}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to generate upload URL: {str(e)}")
        except Exception as e:
            print(f"❌ Error generating upload URL: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to generate upload URL: {str(e)}")
    
    def generate_presigned_download_url(
        self,
        file_path: str,
        expires_in: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a presigned URL for downloading/viewing a file from Supabase Storage.
        
        Args:
            file_path: Path to the file in storage
            expires_in: Optional custom expiration time in seconds (default: 3600)
            
        Returns:
            Dictionary containing download URL and expiration info
            
        Raises:
            RuntimeError: If URL generation fails
        """
        expiry = expires_in or 3600  # Default 1 hour
        
        try:
            # Create signed URL for download using Supabase Storage API
            url = f"{settings.SUPABASE_URL}/storage/v1/object/sign/{self._bucket_name}/{file_path}"
            
            response = httpx.post(
                url,
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": expiry},
                timeout=30.0
            )
            
            print(f"📥 Supabase download URL response status: {response.status_code}")
            print(f"📥 Supabase download URL response: {response.text}")
            
            if response.status_code not in [200, 201]:
                raise ValueError(f"Failed to generate signed download URL: {response.text}")
            
            signed_data = response.json()
            signed_url = signed_data.get("signedURL") or signed_data.get("signedUrl") or signed_data.get("signed_url")
            
            if not signed_url:
                raise ValueError(f"No signed URL in response: {signed_data}")
            
            # Make the URL absolute if it's relative
            if signed_url.startswith("/"):
                download_url = f"{settings.SUPABASE_URL}/storage/v1{signed_url}"
            else:
                download_url = signed_url
            
            return {
                "download_url": download_url,
                "expires_in": expiry
            }
            
        except httpx.HTTPError as e:
            print(f"❌ HTTP Error generating download URL: {str(e)}")
            raise RuntimeError(f"Failed to generate download URL: {str(e)}")
        except Exception as e:
            print(f"❌ Error generating download URL: {str(e)}")
            raise RuntimeError(f"Failed to generate download URL: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from Supabase Storage.
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            True if deletion was successful or file doesn't exist
            
        Raises:
            RuntimeError: If deletion fails for reasons other than file not found
        """
        try:
            # Delete file using Supabase Storage API
            url = f"{settings.SUPABASE_URL}/storage/v1/object/{self._bucket_name}/{file_path}"
            
            response = httpx.delete(
                url,
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                },
                timeout=30.0
            )
            
            # 404 means file doesn't exist, which is fine for deletion
            if response.status_code == 404:
                print(f"File {file_path} not found in storage (already deleted or never uploaded)")
                return True
            
            if response.status_code not in [200, 204]:
                raise ValueError(f"Failed to delete file: {response.text}")
            
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to delete file: {str(e)}")
    
    def get_file_url(self, file_path: str) -> str:
        """
        Get the public URL for a file (for public buckets).
        For private buckets, use generate_presigned_download_url instead.
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            Public URL to the file
        """
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self._bucket_name}/{file_path}"
    
    def upload_file(
        self,
        file_path: str,
        file_data: bytes,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Upload a file directly to Supabase Storage (server-side upload).
        
        Args:
            file_path: Destination path in storage
            file_data: File content as bytes
            content_type: MIME type of the file
            
        Returns:
            Dictionary with upload result
            
        Raises:
            RuntimeError: If upload fails
        """
        try:
            url = f"{settings.SUPABASE_URL}/storage/v1/object/{self._bucket_name}/{file_path}"
            
            response = httpx.post(
                url,
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                    "Content-Type": content_type,
                },
                content=file_data,
                timeout=60.0
            )
            
            if response.status_code not in [200, 201]:
                raise ValueError(f"Failed to upload file: {response.text}")
            
            return {
                "success": True,
                "file_path": file_path,
                "response": response.json() if response.text else {}
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload file: {str(e)}")
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in Supabase Storage.
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            url = f"{settings.SUPABASE_URL}/storage/v1/object/{self._bucket_name}/{file_path}"
            
            response = httpx.head(
                url,
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                },
                timeout=10.0
            )
            
            return response.status_code == 200
        except Exception:
            return False


# Singleton instance
storage_service = StorageService()
