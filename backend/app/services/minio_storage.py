"""Small MinIO adapter used by ingestion and future media API routes."""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class MinioStorage:
    def __init__(self) -> None:
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def object_exists(self, object_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise

    def upload_if_missing(self, *, source_path: Path, object_key: str, mime_type: str) -> bool:
        """Upload only when the deterministic content key is absent.

        Returns ``True`` when bytes were uploaded and ``False`` when the object
        already existed. Existing objects are never overwritten.
        """

        if self.object_exists(object_key):
            return False
        self.client.fput_object(
            self.bucket,
            object_key,
            str(source_path),
            content_type=mime_type,
        )
        return True

    def upload_bytes_if_missing(self, *, data: bytes, object_key: str, mime_type: str) -> bool:
        """Upload extracted in-memory media only when its content key is absent."""

        if self.object_exists(object_key):
            return False
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=mime_type,
        )
        return True

    def presigned_download_url(self, object_key: str, expires_seconds: int = 600) -> str:
        """Create a short-lived browser URL without exposing local file paths."""

        public_client = self.client
        if settings.minio_public_endpoint and settings.minio_public_endpoint != settings.minio_endpoint:
            public_client = Minio(
                settings.minio_public_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                region="us-east-1",
            )
        return public_client.presigned_get_object(
            self.bucket,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )
