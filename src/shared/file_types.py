"""Shared document type classification used at file-processing seams."""

from pathlib import Path
from typing import Optional


_TEXT_APPLICATION_TYPES = {
    "application/csv",
    "application/json",
    "application/sql",
    "application/xml",
    "application/x-ndjson",
    "application/x-yaml",
    "application/yaml",
}
_TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".rst",
    ".sql",
    ".text",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def is_text_document(content_type: Optional[str], filename: Optional[str] = None) -> bool:
    """Return whether a document can be safely decoded as text."""
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type.startswith("text/") or normalized_type in _TEXT_APPLICATION_TYPES:
        return True
    return bool(filename and Path(filename).suffix.lower() in _TEXT_EXTENSIONS)
