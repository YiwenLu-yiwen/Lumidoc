import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.storage.storage_factory import get_storage_base_path


def test_s3_prefix_does_not_use_container_local_directory(monkeypatch) -> None:
    monkeypatch.setenv("UPLOAD_DIR", "/app/uploads")
    monkeypatch.delenv("S3_UPLOAD_PREFIX", raising=False)

    assert get_storage_base_path("s3", "upload") == "uploads"
    assert get_storage_base_path("local", "upload") == "/app/uploads"


def test_s3_prefix_can_be_configured_independently(monkeypatch) -> None:
    monkeypatch.setenv("S3_CONTENT_PREFIX", "documents/content")

    assert get_storage_base_path("s3", "content") == "documents/content"
