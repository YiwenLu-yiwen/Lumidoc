import pytest

from src.modules.chat.chat_engine import ChatEngine


def make_chat_engine() -> ChatEngine:
    return ChatEngine.__new__(ChatEngine)


def test_regular_rag_context_is_not_returned_as_the_final_answer() -> None:
    engine = make_chat_engine()
    context = "Document chunk one.\nDocument chunk two."

    direct_answer = engine._build_context_direct_answer(
        "Summarize the document", context
    )

    assert direct_answer is None


def test_isolation_probe_can_still_extract_its_project_marker() -> None:
    engine = make_chat_engine()
    context = "Unique secret code: VITEST_SECRET_123_A1"

    direct_answer = engine._build_context_direct_answer(
        "Return the exact secret code", context
    )

    assert direct_answer == "VITEST_SECRET_123_A1"


@pytest.mark.asyncio
async def test_chat_engine_forwards_selected_model_to_llm(monkeypatch) -> None:
    class FailingRagClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("RAG unavailable in unit test")

    class RecordingLLMService:
        received_model = None

        async def process_general(self, prompt: str, **kwargs) -> str:
            self.received_model = kwargs.get("model")
            return "model response"

    monkeypatch.setattr(
        "src.modules.chat.chat_engine.httpx.AsyncClient", FailingRagClient
    )
    llm_service = RecordingLLMService()
    engine = ChatEngine(llm_service=llm_service)

    chunks = [
        chunk
        async for chunk in engine.chat_stream(
            message="hello",
            project_id="project-1",
            model="qwen3:8b",
        )
    ]

    assert chunks == ["model response"]
    assert llm_service.received_model == "qwen3:8b"
