from typing import Any


def describe_route(route: Any) -> str | None:
    """Return a safe log description for public FastAPI route objects."""
    path = getattr(route, "path", None)
    if not path:
        return None

    methods = getattr(route, "methods", None)
    if methods:
        return f"{path} [{', '.join(sorted(methods))}]"
    return f"{path} [WebSocket]"
