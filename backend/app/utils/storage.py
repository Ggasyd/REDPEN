"""Storage service for MinIO/S3."""
import io
import os
from typing import Optional, BinaryIO
from uuid import uuid4
from minio import Minio
from minio.error import S3Error
from app.config import settings


class StorageService:
    """Service for object storage (MinIO/S3)."""

    def __init__(self):
        self._client = None
        self.bucket_name = None

    def _initialize(self):
        """Lazy initialization of storage client."""
        if self._client is not None:
            return

        if settings.storage_type == "minio":
            self._client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
            self.bucket_name = settings.minio_bucket_name
        else:
            # TODO: Add S3 support
            raise NotImplementedError("S3 storage not yet implemented")

        self._ensure_bucket()

    @property
    def client(self):
        """Get MinIO client, initializing if needed."""
        if self._client is None:
            self._initialize()
        return self._client

    def _ensure_bucket(self) -> None:
        """Ensure bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            print(f"Error ensuring bucket: {e}")

    def upload_file(
        self,
        file_data: BinaryIO,
        object_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        folder: str = "uploads",
    ) -> str:
        """Upload a file to storage.

        Args:
            file_data: File-like object
            object_name: Optional object name (generated if None)
            content_type: MIME type
            folder: Folder path in bucket

        Returns:
            Storage URL
        """
        if object_name is None:
            object_name = f"{folder}/{uuid4()}"
        else:
            object_name = f"{folder}/{object_name}"

        # Get file size
        file_data.seek(0, os.SEEK_END)
        file_size = file_data.tell()
        file_data.seek(0)

        try:
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_data,
                file_size,
                content_type=content_type,
            )
            return f"{self.bucket_name}/{object_name}"
        except S3Error as e:
            raise Exception(f"Failed to upload file: {e}")

    def upload_bytes(
        self,
        data: bytes,
        object_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        folder: str = "uploads",
    ) -> str:
        """Upload bytes to storage."""
        file_data = io.BytesIO(data)
        return self.upload_file(file_data, object_name, content_type, folder)

    def download_file(self, storage_url: str) -> bytes:
        """Download a file from storage.

        Args:
            storage_url: Storage URL (bucket_name/object_name)

        Returns:
            File bytes
        """
        # Remove bucket name from URL
        object_name = storage_url.replace(f"{self.bucket_name}/", "")

        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise Exception(f"Failed to download file: {e}")

    def delete_file(self, storage_url: str) -> None:
        """Delete a file from storage."""
        object_name = storage_url.replace(f"{self.bucket_name}/", "")

        try:
            self.client.remove_object(self.bucket_name, object_name)
        except S3Error as e:
            raise Exception(f"Failed to delete file: {e}")

    def get_presigned_url(self, storage_url: str, expires: int = 3600) -> str:
        """Get a presigned URL for temporary access.

        Args:
            storage_url: Storage URL
            expires: Expiration time in seconds

        Returns:
            Presigned URL
        """
        object_name = storage_url.replace(f"{self.bucket_name}/", "")

        try:
            url = self.client.presigned_get_object(
                self.bucket_name, object_name, expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise Exception(f"Failed to generate presigned URL: {e}")


from datetime import timedelta

# Global storage instance
storage = StorageService()
