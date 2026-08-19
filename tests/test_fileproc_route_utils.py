import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.fileproc.route_utils import describe_route


class RouteWithoutPath:
    pass


class HttpRoute:
    path = "/healthz"
    methods = {"GET", "HEAD"}


class WebSocketRoute:
    path = "/ws"


def test_describe_route_ignores_fastapi_internal_router_objects() -> None:
    assert describe_route(RouteWithoutPath()) is None


def test_describe_route_handles_http_and_websocket_routes() -> None:
    assert describe_route(HttpRoute()) == "/healthz [GET, HEAD]"
    assert describe_route(WebSocketRoute()) == "/ws [WebSocket]"
