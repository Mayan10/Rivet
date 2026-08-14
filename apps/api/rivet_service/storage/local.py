"""Local-disk storage for dev/self-hosted use (docs/saas-buildout.md
section 6). Has no native "presigned URL" concept the way S3 does, so
this fakes the same interface with a signed, expiring token
(auth/tokens.py, purpose="artifact_download") embedded in a URL that
routes back through the API (api/v1/local_artifacts.py) rather than a
direct file path -- keeps the StorageAdapter interface identical for
both backends, and the file stays exactly as "private until presigned"
as the S3 backend's bucket.
"""

from __future__ import annotations

from pathlib import Path

from ..auth.tokens import generate_token
from .base import StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, base_dir: str, *, secret_key: str, public_base_url: str) -> None:
        self._base_dir = Path(base_dir)
        self._secret_key = secret_key
        self._public_base_url = public_base_url.rstrip("/")

    def _path_for(self, key: str) -> Path:
        base = self._base_dir.resolve()
        path = (self._base_dir / key).resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"Refusing to access a path outside the storage directory: {key!r}")
        return path

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path_for(key).unlink(missing_ok=True)

    def presigned_download_url(self, key: str, *, expires_in: int) -> str:
        token = generate_token(self._secret_key, purpose="artifact_download", subject=key, ttl_seconds=expires_in)
        return f"{self._public_base_url}/api/v1/local-artifacts/{token}"
