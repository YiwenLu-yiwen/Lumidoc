from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_graph_api_does_not_bypass_authenticated_gateway() -> None:
    graph_api = (REPO_ROOT / "frontend" / "src" / "api" / "graph.ts").read_text(
        encoding="utf-8"
    )

    assert "http://localhost:8006" not in graph_api
    assert "apiClient.get<GraphApiPayload>" in graph_api
