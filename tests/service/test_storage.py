import pytest

from rivet_service.storage.local import LocalStorageAdapter
from rivet_service.storage.s3 import S3StorageAdapter

from .conftest import minio_is_reachable


@pytest.fixture
def local_adapter(tmp_path):
    return LocalStorageAdapter(str(tmp_path), secret_key="test-secret", public_base_url="http://localhost:8000")


def test_local_put_and_get_round_trip(local_adapter):
    local_adapter.put("a/b/c.dxf", b"hello world", content_type="application/dxf")
    assert local_adapter.get("a/b/c.dxf") == b"hello world"


def test_local_delete_removes_the_file(local_adapter):
    local_adapter.put("a.txt", b"data", content_type="text/plain")
    local_adapter.delete("a.txt")
    with pytest.raises(FileNotFoundError):
        local_adapter.get("a.txt")


def test_local_rejects_path_traversal(local_adapter):
    with pytest.raises(ValueError, match="outside the storage directory"):
        local_adapter.put("../../etc/passwd", b"pwned", content_type="text/plain")


def test_local_presigned_url_embeds_a_verifiable_token(local_adapter):
    from rivet_service.auth.tokens import verify_token

    url = local_adapter.presigned_download_url("a/b/c.dxf", expires_in=60)
    assert url.startswith("http://localhost:8000/api/v1/local-artifacts/")
    token = url.rsplit("/", 1)[-1]
    assert verify_token("test-secret", token, expected_purpose="artifact_download") == "a/b/c.dxf"


def test_local_presigned_url_rejects_wrong_secret(local_adapter):
    from rivet_service.auth.tokens import TokenError, verify_token

    url = local_adapter.presigned_download_url("a/b/c.dxf", expires_in=60)
    token = url.rsplit("/", 1)[-1]
    with pytest.raises(TokenError):
        verify_token("a-different-secret", token, expected_purpose="artifact_download")


@pytest.fixture
def s3_adapter():
    if not minio_is_reachable():
        pytest.skip("No MinIO reachable at localhost:9000")
    adapter = S3StorageAdapter(
        "rivet-test-bucket",
        endpoint_url="http://localhost:9000",
        access_key="rivet",
        secret_key="rivet-dev-secret",
        region="us-east-1",
    )
    adapter.ensure_bucket()
    return adapter


def test_s3_put_and_get_round_trip(s3_adapter):
    s3_adapter.put("a/b/c.dxf", b"hello from s3", content_type="application/dxf")
    assert s3_adapter.get("a/b/c.dxf") == b"hello from s3"
    s3_adapter.delete("a/b/c.dxf")


def test_s3_presigned_url_is_actually_fetchable(s3_adapter):
    import urllib.request

    s3_adapter.put("fetchable.dxf", b"real bytes", content_type="application/dxf")
    url = s3_adapter.presigned_download_url("fetchable.dxf", expires_in=60)
    with urllib.request.urlopen(url) as resp:
        assert resp.read() == b"real bytes"
    s3_adapter.delete("fetchable.dxf")


def test_s3_delete_removes_the_object(s3_adapter):
    import botocore.exceptions

    s3_adapter.put("to-delete.txt", b"data", content_type="text/plain")
    s3_adapter.delete("to-delete.txt")
    with pytest.raises(botocore.exceptions.ClientError):
        s3_adapter.get("to-delete.txt")
