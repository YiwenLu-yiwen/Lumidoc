import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.file_types import is_text_document


def test_text_document_detection_uses_mime_type() -> None:
    assert is_text_document("text/plain", "document.bin")
    assert is_text_document("application/json; charset=utf-8")
    assert not is_text_document("application/pdf", "document.pdf")


def test_text_document_detection_falls_back_to_extension() -> None:
    assert is_text_document("application/octet-stream", "notes.md")
    assert not is_text_document("application/octet-stream", "archive.zip")
