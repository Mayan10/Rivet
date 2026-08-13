"""S3-compatible storage (docs/saas-buildout.md section 6): real AWS S3
(the decided deploy target) or MinIO for local/self-hosted use, by
pointing ``endpoint_url`` at MinIO instead of leaving it unset. Same
``boto3`` client either way -- MinIO implements the S3 API.
"""

from __future__ import annotations

import boto3
from botocore.client import Config as BotoConfig

from .base import StorageAdapter


class S3StorageAdapter(StorageAdapter):
    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(signature_version="s3v4"),
        )

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_download_url(self, key: str, *, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in
        )

    def ensure_bucket(self) -> None:
        """Dev/test convenience -- create the bucket if it doesn't exist
        yet. Real AWS S3 buckets are provisioned out of band (Terraform/
        console), this matters for a fresh local MinIO only.
        """
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        if self._bucket not in existing:
            self._client.create_bucket(Bucket=self._bucket)
