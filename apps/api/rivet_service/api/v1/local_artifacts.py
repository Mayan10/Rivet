"""Serves the signed download links storage/local.py's presigned URLs
point at. Only meaningful when ``storage_backend="local"`` -- the S3
backend's presigned URLs point directly at S3/MinIO, never at this API.
"""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Response

from ...auth.tokens import TokenError, verify_token
from ...config import get_settings
from ...storage import get_storage_adapter
from ..errors import ApiError

router = APIRouter(prefix="/local-artifacts", tags=["local-artifacts"])


@router.get("/{token}")
def download_local_artifact(token: str) -> Response:
    settings = get_settings()
    try:
        key = verify_token(settings.secret_key, token, expected_purpose="artifact_download")
    except TokenError as exc:
        raise ApiError("not_found", "Invalid or expired download link.", status_code=404) from exc

    storage = get_storage_adapter()
    try:
        data = storage.get(key)
    except (FileNotFoundError, ValueError) as exc:
        raise ApiError("not_found", "Artifact not found.", status_code=404) from exc

    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type)
