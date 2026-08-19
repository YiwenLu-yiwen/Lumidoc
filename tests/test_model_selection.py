import pytest
from pydantic import ValidationError

from src.modules.chat.chat_manager import ChatManager
from src.modules.llm.api.models import ChatGenerationRequest, ChatMessage
from src.modules.llm.routes.router import (
    EmbeddingRequest,
    create_embeddings,
    generate_chat,
    router as llm_router,
)


def test_llm_chat_request_rejects_invalid_model_id() -> None:
    with pytest.raises(ValidationError):
        ChatGenerationRequest(
            messages=[ChatMessage(role="user", content="hello")],
            model="model name; rm -rf",
        )


@pytest.mark.asyncio
async def test_chat_manager_forwards_selected_model_to_engine() -> None:
    class RecordingEngine:
        received_model = None

        async def chat_stream(self, **kwargs):
            self.received_model = kwargs.get("model")
            yield "ok"

    engine = RecordingEngine()
    manager = ChatManager(llm_service=None, graph_service=None, chat_engine=engine)

    chunks = [
        chunk
        async for chunk in manager.process_message_stream(
            project_id="project-1",
            message="hello",
            model="qwen3:8b",
        )
    ]

    assert chunks == ["ok"]
    assert engine.received_model == "qwen3:8b"


@pytest.mark.asyncio
async def test_llm_chat_route_forwards_selected_model_to_adapter() -> None:
    class RecordingLLMService:
        received_model = None

        async def generate_chat(self, messages, **kwargs):
            self.received_model = kwargs.get("model")
            return "selected model response"

    service = RecordingLLMService()
    request = ChatGenerationRequest(
        messages=[ChatMessage(role="user", content="hello")],
        model="qwen3:8b",
    )

    response = await generate_chat(request=request, llm_service=service)

    assert response.message.content == "selected model response"
    assert service.received_model == "qwen3:8b"


def test_llm_triples_endpoint_is_registered_once() -> None:
    triples_routes = [
        route
        for route in llm_router.routes
        if route.path == "/api/v1/llm/triples" and "POST" in route.methods
    ]

    assert len(triples_routes) == 1


@pytest.mark.asyncio
async def test_embedding_route_forwards_selected_embedding_model() -> None:
    class RecordingLLMService:
        received_model = None

        async def create_embeddings(self, texts, **kwargs):
            self.received_model = kwargs.get("model")
            return [[0.1, 0.2, 0.3] for _ in texts]

    service = RecordingLLMService()
    request = EmbeddingRequest(texts=["hello"], model="nomic-embed-text")

    response = await create_embeddings(request=request, llm_service=service)

    assert response.embeddings == [[0.1, 0.2, 0.3]]
    assert service.received_model == "nomic-embed-text"
