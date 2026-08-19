from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


def load_services() -> dict:
    with COMPOSE_PATH.open(encoding="utf-8") as compose_file:
        return yaml.safe_load(compose_file)["services"]


def test_compose_matches_current_application_architecture() -> None:
    services = load_services()

    assert "gateway_service" in services
    assert "project_service" in services
    assert "frontend" in services
    assert "ollama" in services
    assert "ollama_models" in services
    assert "webui_backend" not in services
    assert "webui_frontend" not in services

    assert services["rag_service"]["build"]["dockerfile"] == (
        "src/modules/lightraglocal/Dockerfile"
    )
    assert services["frontend"]["build"]["context"] == "./frontend"


def test_every_compose_build_target_exists() -> None:
    for service_name, service in load_services().items():
        build = service.get("build")
        if not build:
            continue

        if isinstance(build, str):
            context = REPO_ROOT / build
            dockerfile = context / "Dockerfile"
        else:
            context = REPO_ROOT / build["context"]
            dockerfile = context / build.get("dockerfile", "Dockerfile")

        assert context.is_dir(), f"{service_name} build context is missing: {context}"
        assert dockerfile.is_file(), (
            f"{service_name} Dockerfile is missing: {dockerfile}"
        )


def test_frontend_image_is_a_health_checked_production_build() -> None:
    dockerfile = (REPO_ROOT / "frontend/Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:20-slim AS build" in dockerfile
    assert "FROM nginx:" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'CMD ["nginx", "-g", "daemon off;"]' in dockerfile
    assert "npm run dev" not in dockerfile
    assert (REPO_ROOT / "frontend/.dockerignore").is_file()
    assert (REPO_ROOT / "frontend/nginx.conf").is_file()


def test_every_runnable_backend_module_is_containerized() -> None:
    services = load_services()
    compose_dockerfiles = {
        service["build"]["dockerfile"]
        for service in services.values()
        if isinstance(service.get("build"), dict)
        and service["build"].get("dockerfile", "").startswith("src/modules/")
    }

    runnable_modules = {
        module_dir.name
        for module_dir in (REPO_ROOT / "src/modules").iterdir()
        if module_dir.is_dir() and (module_dir / "main.py").is_file()
    }
    assert runnable_modules

    for module_name in runnable_modules:
        dockerfile_path = f"src/modules/{module_name}/Dockerfile"
        assert (REPO_ROOT / dockerfile_path).is_file(), module_name
        assert dockerfile_path in compose_dockerfiles, module_name


def test_backend_images_share_the_standard_healthcheck() -> None:
    healthcheck_script = REPO_ROOT / "scripts/docker_healthcheck.py"
    assert healthcheck_script.is_file()

    for module_dir in (REPO_ROOT / "src/modules").iterdir():
        if not (module_dir / "main.py").is_file():
            continue
        dockerfile = module_dir / "Dockerfile"
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        assert "HEALTHCHECK" in dockerfile_text, module_dir.name
        assert "/app/scripts/docker_healthcheck.py" in dockerfile_text, (
            module_dir.name
        )


def test_compose_contains_no_removed_application_names_or_paths() -> None:
    compose_text = COMPOSE_PATH.read_text(encoding="utf-8").lower()

    assert "lumidoc_webui" not in compose_text
    assert "webui_" not in compose_text
    assert "src/modules/rag/" not in compose_text


def test_container_builds_do_not_copy_local_secrets() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    ignored_paths = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env" in ignored_paths
    assert "**/*.pem" in ignored_paths
    assert "**/*.key" in ignored_paths

    for dockerfile in REPO_ROOT.glob("**/Dockerfile"):
        if "node_modules" in dockerfile.parts:
            continue
        dockerfile_text = dockerfile.read_text(encoding="utf-8").lower()
        assert "copy .env" not in dockerfile_text, (
            f"local secrets must not be copied into {dockerfile}"
        )


def test_compose_requires_credentials_instead_of_shipping_password_defaults() -> None:
    compose_text = COMPOSE_PATH.read_text(encoding="utf-8")

    for insecure_default in (
        "POSTGRES_PASSWORD:-postgres",
        "NEO4J_PASSWORD:-123456789",
        "REDIS_PASSWORD:-123456789",
        "S3_ACCESS_KEY:-minioadmin",
        "S3_SECRET_KEY:-minioadmin",
        "service-token-for-internal-use",
    ):
        assert insecure_default not in compose_text

    for line in compose_text.splitlines():
        if any(
            credential_name in line
            for credential_name in (
                "PASSWORD=",
                "SECRET_KEY=",
                "ACCESS_KEY=",
                "AUTH_TOKEN=",
            )
        ):
            assert "${" in line, f"literal credential in Compose: {line.strip()}"

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!.env.example" in gitignore.splitlines()
    assert (REPO_ROOT / ".env.example").is_file()


def test_ocr_models_are_scoped_to_the_file_processor_image() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    fileproc_ignore = (
        REPO_ROOT / "src/modules/fileproc/Dockerfile.dockerignore"
    ).read_text(encoding="utf-8")

    assert "src/models" in dockerignore.splitlines()
    assert "src/models" not in fileproc_ignore.splitlines()


def test_root_requirements_containers_can_build_native_dependencies() -> None:
    for dockerfile in (REPO_ROOT / "src/modules").glob("*/Dockerfile"):
        dockerfile_text = dockerfile.read_text(encoding="utf-8").lower()
        if "copy requirements.txt" not in dockerfile_text:
            continue

        assert dockerfile_text.startswith("from python:3.11-slim"), dockerfile
        assert "build-essential" in dockerfile_text, dockerfile


def test_llm_container_uses_the_shared_healthcheck_without_curl() -> None:
    dockerfile = REPO_ROOT / "src/modules/llm/Dockerfile"
    dockerfile_text = dockerfile.read_text(encoding="utf-8").lower()

    assert "docker_healthcheck.py" in dockerfile_text
    assert "curl" not in dockerfile_text


def test_lightweight_images_use_shared_core_and_module_requirements() -> None:
    shared_requirements = REPO_ROOT / "requirements/service-core.txt"
    assert shared_requirements.is_file()

    for module_name in {
        "auth",
        "chat",
        "gateway",
        "graph",
        "llm",
        "monitoring",
        "project",
        "question",
    }:
        module_requirements = (
            REPO_ROOT / f"src/modules/{module_name}/requirements.txt"
        )
        dockerfile_text = (
            REPO_ROOT / f"src/modules/{module_name}/Dockerfile"
        ).read_text(encoding="utf-8")

        assert module_requirements.is_file(), module_name
        assert "requirements/service-core.txt" in dockerfile_text, module_name
        assert f"src/modules/{module_name}/requirements.txt" in dockerfile_text, (
            module_name
        )
        assert "COPY requirements.txt" not in dockerfile_text, module_name
        assert "apt-get purge -y --auto-remove build-essential" in (
            dockerfile_text
        ), module_name


def test_published_ports_are_not_shared_by_local_replicas() -> None:
    for service_name, service in load_services().items():
        if not service.get("ports"):
            continue

        replicas = service.get("deploy", {}).get("replicas", 1)
        assert replicas == 1, (
            f"{service_name} publishes a fixed host port and cannot have "
            f"{replicas} local replicas"
        )


def test_compose_uses_container_network_addresses() -> None:
    services = load_services()
    gateway_environment = set(services["gateway_service"]["environment"])

    for service_name, port in {
        "AUTH": 8007,
        "CHAT": 8001,
        "FILE": 8004,
        "FILEPROC": 8005,
        "GRAPH": 8003,
        "RAG": 8006,
        "LLM": 8080,
        "MONITORING": 8008,
        "PROJECT": 8020,
        "QUESTION": 8002,
    }.items():
        compose_name = {
            "RAG": "rag_service",
            "LLM": "llm_service",
        }.get(service_name, f"{service_name.lower()}_service")
        assert (
            f"{service_name}_SERVICE_URL=http://{compose_name}:{port}"
            in gateway_environment
        )

    for service_name in ("project_service", "chat_service", "question_service"):
        environment = set(services[service_name]["environment"])
        assert any(
            value.startswith("POSTGRES_URL=") and "@db:5432/" in value
            for value in environment
        ), service_name

    project_environment = set(services["project_service"]["environment"])
    assert "AUTH_SERVICE_URL=http://auth_service:8007" in project_environment

    chat_environment = set(services["chat_service"]["environment"])
    assert "GRAPH_SERVICE_URL=http://graph_service:8003" in chat_environment

    auth_environment = set(services["auth_service"]["environment"])
    assert "POSTGRES_HOST=db" in auth_environment
    assert "POSTGRES_PORT=5432" in auth_environment

    file_environment = set(services["file_service"]["environment"])
    assert "POSTGRES_PORT=5432" in file_environment
    assert "AUTH_SERVICE_URL=http://auth_service:8007" in file_environment
    assert "PROJECT_SERVICE_URL=http://project_service:8020" in file_environment
    assert "FILEPROC_SERVICE_URL=http://fileproc_service:8005" in file_environment

    rag_environment = set(services["rag_service"]["environment"])
    assert "FILE_SERVICE_URL=http://file_service:8004" in rag_environment
    assert "PROJECT_SERVICE_URL=http://project_service:8020" in rag_environment

    fileproc_environment = set(services["fileproc_service"]["environment"])
    assert "MINIO_ENDPOINT=minio:9000" in fileproc_environment
    assert "POSTGRES_PORT=5432" in fileproc_environment
    assert any(
        value.startswith("POSTGRES_URL=") and "@db:5432/" in value
        for value in fileproc_environment
    )
    assert "FILE_SERVICE_URL=http://file_service:8004" in fileproc_environment

    for service_name in ("rag_service", "llm_service"):
        environment = set(services[service_name]["environment"])
        assert "OLLAMA_API_URL=http://ollama:11434" in environment

    rag_environment = set(services["rag_service"]["environment"])
    assert "GATEWAY_URL=http://gateway_service:8888" in rag_environment
    assert "OLLAMA_EMBEDDING_URL=http://ollama:11434" in rag_environment
    assert "EMBEDDING_DIM=${OLLAMA_EMBEDDING_DIM:-768}" in rag_environment

    llm_environment = set(services["llm_service"]["environment"])
    assert "OLLAMA_URL=http://ollama:11434" in llm_environment
    assert "LLM_MODEL_NAME=${OLLAMA_CHAT_MODEL:-qwen3:1.7b}" in llm_environment
    assert (
        "DEFAULT_EMBEDDING_MODEL=${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}"
        in llm_environment
    )


def test_compose_provisions_models_without_host_or_platform_dependencies() -> None:
    compose_text = COMPOSE_PATH.read_text(encoding="utf-8").lower()
    services = load_services()

    for forbidden in (
        "host.docker.internal",
        "host-gateway",
        "darwin",
        "macos",
        "apple",
        "platform: linux/amd64",
        "platform: linux/arm64",
    ):
        assert forbidden not in compose_text

    assert services["ollama"]["image"].startswith("ollama/ollama:")
    assert services["ollama"]["healthcheck"]
    assert "ollama_data:/root/.ollama" in services["ollama"]["volumes"]

    model_loader = services["ollama_models"]
    assert model_loader["image"] == services["ollama"]["image"]
    assert model_loader["restart"] == "no"
    assert model_loader["depends_on"]["ollama"]["condition"] == "service_healthy"
    loader_command = "\n".join(model_loader["command"])
    assert loader_command.count("ollama pull") == 2
    assert "ollama list" in loader_command

    llm_dependency = services["llm_service"]["depends_on"]["ollama_models"]
    assert llm_dependency["condition"] == "service_completed_successfully"


def test_one_command_scripts_only_orchestrate_docker_compose() -> None:
    for script_name in (
        "start_services.sh",
        "stop_services.sh",
    ):
        script = REPO_ROOT / script_name
        text = script.read_text(encoding="utf-8").lower()
        assert "docker compose" in text, script_name
        for forbidden in (
            "conda",
            "sw_vers",
            "darwin",
            "macos",
            "host.docker.internal",
            "npm run",
            "python -m src.modules",
        ):
            assert forbidden not in text, (script_name, forbidden)

    assert not (REPO_ROOT / "start_services_linux.sh").exists()
    assert not (REPO_ROOT / "stop_services_linux.sh").exists()


def test_file_service_images_include_shared_runtime_dependencies() -> None:
    for service_name in ("file", "fileproc"):
        requirements = (
            REPO_ROOT / f"src/modules/{service_name}/requirements.txt"
        ).read_text(encoding="utf-8")
        assert "redis>=" in requirements, service_name
        assert "psutil>=" in requirements, service_name
        assert "boto3>=" in requirements, service_name
        assert "PyYAML>=" in requirements, service_name

    fileproc_requirements = (
        REPO_ROOT / "src/modules/fileproc/requirements.txt"
    ).read_text(encoding="utf-8")
    fileproc_runtime_requirements = (
        REPO_ROOT / "src/modules/fileproc/requirements-runtime.txt"
    ).read_text(encoding="utf-8")
    assert "docling==" in fileproc_requirements
    assert "docling-core==" in fileproc_requirements
    assert "torch==" in fileproc_requirements
    assert "torchvision==" in fileproc_requirements
    assert "aiohttp>=" in fileproc_runtime_requirements
    assert "asyncpg>=" in fileproc_runtime_requirements
    assert "psycopg[binary]>=" in fileproc_runtime_requirements

    fileproc_dockerfile = (
        REPO_ROOT / "src/modules/fileproc/Dockerfile"
    ).read_text(encoding="utf-8")
    assert "--timeout 120" in fileproc_dockerfile
    assert "--retries 5" in fileproc_dockerfile
