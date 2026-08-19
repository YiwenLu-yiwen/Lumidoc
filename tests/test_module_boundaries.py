from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_python_modules_do_not_collide_with_same_named_packages() -> None:
    collisions = []
    for module_file in (REPO_ROOT / "src").rglob("*.py"):
        package_dir = module_file.with_suffix("")
        if package_dir.is_dir():
            collisions.append(
                str(module_file.relative_to(REPO_ROOT))
            )

    assert collisions == []


def test_fileproc_uses_typed_settings_for_storage_connections() -> None:
    from src.modules.fileproc.config import settings

    assert settings.content_dir
    assert settings.minio_endpoint
    assert settings.minio_access_key
    assert settings.minio_secret_key
    assert settings.redis_host
    assert settings.redis_port
    assert settings.get_redis_url().startswith("redis://")

    processor_source = (
        REPO_ROOT / "src/modules/fileproc/services/file_processor.py"
    ).read_text(encoding="utf-8")
    for legacy_name in (
        "settings.CONTENT_DIR",
        "settings.MINIO_ENDPOINT",
        "settings.MINIO_ACCESS_KEY",
        "settings.MINIO_SECRET_KEY",
    ):
        assert legacy_name not in processor_source

    queue_source = (
        REPO_ROOT / "src/modules/fileproc/services/queue_service.py"
    ).read_text(encoding="utf-8")
    assert 'logger.info(f"正在连接到Redis: {redis_url}")' not in queue_source


def module_python_source(module_name: str) -> str:
    module_dir = REPO_ROOT / "src/modules" / module_name
    return "\n".join(
        path.read_text(encoding="utf-8") for path in module_dir.rglob("*.py")
    )


def test_chat_uses_shared_clients_instead_of_graph_or_rag_internals() -> None:
    chat_source = module_python_source("chat")

    assert "src.modules.graph" not in chat_source
    assert "src.modules.lightraglocal" not in chat_source
    assert "src.shared.clients" in chat_source


def test_project_uses_shared_auth_boundary() -> None:
    project_source = module_python_source("project")

    assert "src.modules.auth" not in project_source
    assert "src.shared.auth" in project_source


def test_project_access_policy_is_shared_by_file_and_lightrag() -> None:
    shared_policy = REPO_ROOT / "src/shared/project_access.py"
    file_routes = REPO_ROOT / "src/modules/file/routes/file_routes.py"
    rag_routes = (
        REPO_ROOT
        / "src/modules/lightraglocal/routes/enterprise_rag_routes.py"
    )

    assert shared_policy.is_file()
    assert "src.shared.project_access" in file_routes.read_text(encoding="utf-8")
    assert "src.shared.project_access" in rag_routes.read_text(encoding="utf-8")

    file_source = file_routes.read_text(encoding="utf-8")
    assert "require_project_access_dependency" in file_source
    assert "require_service_access" in file_source
