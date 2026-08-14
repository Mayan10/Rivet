"""Storage adapter interface (docs/saas-buildout.md section 6): local
disk and S3 implementations behind the same interface, so
`docker compose up` needs no cloud account. Nothing outside
storage/ (or a route/job that just calls ``get_storage_adapter()``)
should know which backend is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def presigned_download_url(self, key: str, *, expires_in: int) -> str:
        """A short-lived URL a client can download ``key`` from directly,
        without going back through the API (section 6: "the API ... then
        issues a short-lived presigned URL"). Buckets/directories stay
        private; this is the only sanctioned way out.
        """
