from __future__ import annotations

from ..config import get_settings
from .base import StorageAdapter
from .local import LocalStorageAdapter
from .s3 import S3StorageAdapter


def get_storage_adapter() -> StorageAdapter:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3StorageAdapter(
            settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
        )
    return LocalStorageAdapter(
        settings.storage_local_dir, secret_key=settings.secret_key, public_base_url=settings.storage_public_base_url
    )


__all__ = ["LocalStorageAdapter", "S3StorageAdapter", "StorageAdapter", "get_storage_adapter"]
