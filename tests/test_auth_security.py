import inspect
from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from src.modules.auth import auth_api
from src.modules.auth import dependencies as auth_dependencies
from src.modules.auth.auth_service import pwd_context
from src.shared import auth as shared_auth
from src.shared import jwt_utils
from src.shared import service_discovery


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_private_signing_keys_are_not_stored_in_the_repository() -> None:
    key_dir = REPO_ROOT / "src/modules/auth/key"

    assert not (key_dir / "jwt_private_key.pem").exists()
    assert not (key_dir / "jwt_public_key.pem").exists()


def test_docker_context_excludes_nested_key_material() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "**/*.pem" in dockerignore.splitlines()
    assert "**/*.key" in dockerignore.splitlines()


def test_authentication_has_no_unsigned_or_default_admin_bypass() -> None:
    dependency_source = (
        REPO_ROOT / "src/modules/auth/dependencies.py"
    ).read_text(encoding="utf-8")

    assert "verify_signature" not in dependency_source
    assert "SKIP_TOKEN_VERIFICATION" not in dependency_source
    assert "hashed_password=" not in dependency_source


def test_jwt_key_paths_are_deployment_configuration_only() -> None:
    jwt_source = (REPO_ROOT / "src/shared/jwt_utils.py").read_text(
        encoding="utf-8"
    )
    settings_source = (
        REPO_ROOT / "src/shared/config/service_settings.py"
    ).read_text(encoding="utf-8")

    assert "src/modules/auth/key" not in jwt_source
    assert "src/modules/auth/key" not in settings_source


def test_example_environment_contains_placeholders_not_credentials() -> None:
    credential_names = ("PASSWORD", "SECRET", "ACCESS_KEY", "AUTH_TOKEN")

    for raw_line in (REPO_ROOT / ".env.example").read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if any(marker in name for marker in credential_names):
            assert not value or value.startswith("change-me-"), name


def test_shared_auth_dependency_is_async() -> None:
    assert inspect.iscoroutinefunction(shared_auth.get_current_user)


def test_password_reset_requires_current_password() -> None:
    assert "current_password" in auth_api.PasswordReset.model_fields


def test_password_hash_round_trip() -> None:
    password_hash = pwd_context.hash("correct horse battery staple")

    assert password_hash.startswith("$2b$")
    assert pwd_context.verify("correct horse battery staple", password_hash)
    assert not pwd_context.verify("wrong password", password_hash)


def test_auth_dependency_decode_delegates_to_shared_jwt(monkeypatch) -> None:
    expected_payload = {"sub": "42"}
    monkeypatch.setattr(
        auth_dependencies, "decode_jwt_token", lambda token: expected_payload
    )

    assert auth_dependencies.decode_token("encoded-token") == expected_payload


def test_shared_refresh_token_uses_the_configured_signer(monkeypatch) -> None:
    monkeypatch.setattr(jwt_utils, "create_jwt_token", lambda data, expires: "new-token")

    assert jwt_utils.refresh_token("42") == "new-token"


@pytest.mark.asyncio
async def test_password_reset_rejects_invalid_current_password(monkeypatch) -> None:
    class RejectingAuthService:
        async def change_password(
            self, username: str, current_password: str, new_password: str
        ) -> bool:
            return False

    monkeypatch.setattr(auth_api, "auth_service", RejectingAuthService())
    request = auth_api.PasswordReset(
        username="target-user",
        current_password="incorrect-password",
        new_password="new-secure-password",
    )

    with pytest.raises(HTTPException) as error:
        await auth_api.reset_password(request)

    assert error.value.status_code == 401
    assert error.value.detail == "用户名或当前密码错误"


@pytest.mark.asyncio
async def test_shared_auth_accepts_direct_verify_response(monkeypatch) -> None:
    now = datetime.now(timezone.utc).isoformat()

    async def direct_verify_response(**kwargs):
        return {
            "valid": True,
            "user_id": 42,
            "username": "verified-user",
            "email": "verified@example.com",
            "is_active": True,
            "is_superuser": False,
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(service_discovery, "call_service", direct_verify_response)

    user = await shared_auth.get_current_user_from_auth_service("valid-token")

    assert user is not None
    assert user.id == 42
