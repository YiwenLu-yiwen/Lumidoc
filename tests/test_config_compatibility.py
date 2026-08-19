from pydantic import ValidationError

from src.modules.auth.user_model import UserCreate
from src.modules.llm.config.config import LLMServiceSettings
from src.shared.base_config import ServiceBaseSettings
from src.shared.types.chat import ChatMessage, ChatSession


def test_base_settings_read_documented_environment_names(monkeypatch) -> None:
    monkeypatch.setenv("SERVICE_HOST", "127.0.0.77")
    monkeypatch.setenv("SERVICE_PORT", "9120")
    monkeypatch.setenv("CORS_ORIGINS", '["https://lumidoc.test"]')

    settings = ServiceBaseSettings(_env_file=None)

    assert settings.host == "127.0.0.77"
    assert settings.port == 9120
    assert settings.cors_origins == ["https://lumidoc.test"]


def test_llm_settings_read_service_specific_environment_names(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SERVICE_PORT", "9123")
    monkeypatch.setenv("LLM_MODEL_NAME", "test-model")

    settings = LLMServiceSettings(_env_file=None)

    assert settings.port == 9123
    assert settings.llm_model_name == "test-model"


def test_log_prefix_defaults_to_service_name() -> None:
    settings = ServiceBaseSettings(service_name="gateway", _env_file=None)

    assert settings.log_file_prefix == "gateway"


def test_temporary_email_domains_remain_rejected() -> None:
    try:
        UserCreate(
            username="tester",
            email="user@mailinator.com",
            password="secret-password",
        )
    except ValidationError as error:
        assert "不允许使用临时邮箱地址" in str(error)
    else:
        raise AssertionError("temporary email domain should be rejected")


def test_chat_timestamp_and_session_defaults_are_isolated() -> None:
    assert ChatMessage(role="user", content="hello", timestamp="123.5").timestamp == 123.5

    first = ChatSession(session_id="first")
    second = ChatSession(session_id="second")
    first.messages.append(ChatMessage(role="user", content="hello"))

    assert second.messages == []
