import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "logs",
    "node_modules",
    "rag_cache",
    "uploads",
    "venv",
}
IGNORED_PATHS = {Path("libs") / "LightRAG"}
IGNORED_SUFFIXES = {
    ".db",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tsbuildinfo",
    ".webp",
}


def is_repository_owned_path(path: Path) -> bool:
    relative_path = path.relative_to(REPO_ROOT)
    if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
        return False
    if any(
        relative_path == ignored_path or ignored_path in relative_path.parents
        for ignored_path in IGNORED_PATHS
    ):
        return False
    return True


def is_repository_owned_text_file(path: Path) -> bool:
    return (
        is_repository_owned_path(path)
        and path.is_file()
        and path.suffix.lower() not in IGNORED_SUFFIXES
    )


def test_repository_contains_no_legacy_project_names() -> None:
    legacy_acronym = "s" + "tp"
    forbidden_patterns = (
        re.compile(
            rf"(?i:(?<![a-z]){legacy_acronym}"
            rf"(?:[_:-]|db\b|user\b|password\b|\b))"
        ),
        re.compile(
            rf"(?<![A-Za-z])(?:{legacy_acronym}|{legacy_acronym.upper()})(?=[A-Z])"
        ),
        re.compile("open" + r"[ _-]?" + "webui", re.IGNORECASE),
        re.compile("smart" + r"\s+text\s+" + "processing", re.IGNORECASE),
    )
    matches: list[str] = []

    for path in REPO_ROOT.rglob("*"):
        if not is_repository_owned_path(path):
            continue

        relative_path = path.relative_to(REPO_ROOT)
        for forbidden_pattern in forbidden_patterns:
            if forbidden_pattern.search(relative_path.as_posix()):
                matches.append(f"{relative_path}: legacy name in path")

        if not is_repository_owned_text_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for forbidden_pattern in forbidden_patterns:
            if forbidden_pattern.search(text):
                matches.append(
                    f"{relative_path}: {forbidden_pattern.pattern}"
                )

    assert not matches, "Legacy project names remain:\n" + "\n".join(matches)
