"""Typed HTTP client for the graph service boundary."""

import os
from typing import Optional

import httpx

from src.shared.types.graph import GraphAnalysisRequest, GraphData


class GraphServiceClient:
    """Access graph capabilities without importing graph module internals."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        self.base_url = (
            base_url
            or os.getenv("GRAPH_SERVICE_URL", "http://localhost:8003")
        ).rstrip("/")
        self.timeout = timeout

    async def analyze_text(self, request: GraphAnalysisRequest) -> GraphData:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/graph/analyze",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return GraphData.model_validate(response.json())

    async def get_project_graph(self, project_id: str) -> GraphData:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/graph/project/{project_id}"
            )
            response.raise_for_status()
            return GraphData.model_validate(response.json())


default_graph_client = GraphServiceClient()
