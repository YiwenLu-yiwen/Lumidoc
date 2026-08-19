import subprocess
import sys
from pathlib import Path

import pytest

from src.modules.monitoring import main as monitoring_main
from src.shared.utils.redis_queue import RedisQueue


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_redis_queue_reads_connection_environment(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PORT", "6380")

    queue = RedisQueue()

    assert queue.host == "redis.internal"
    assert queue.port == 6380


@pytest.mark.asyncio
async def test_monitoring_health_checker_has_service_checks() -> None:
    health = await monitoring_main.health_checker.check_health()

    assert "monitoring_service" in health["checks"]
    assert "system_resources" in health["checks"]


def test_importing_lightrag_services_does_not_start_async_initialization() -> None:
    script = """
import asyncio

calls = 0
real_run = asyncio.run

async def main():
    global calls

    def forbidden_run(coroutine):
        global calls
        calls += 1
        coroutine.close()
        raise RuntimeError("async initialization during import")

    asyncio.run = forbidden_run
    try:
        import src.modules.lightraglocal.services
    finally:
        asyncio.run = real_run

    assert calls == 0, f"asyncio.run called {calls} time(s) during import"

real_run(main())
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
