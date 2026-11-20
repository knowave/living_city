"""AC12 report-only p95 table. Run: `uv run pytest -q -m perf -s`. Asserts nothing about thresholds."""

import statistics
import time

import pytest

from tests.integration.conftest import pg_engine  # noqa: F401
from tests.integration.live import live_client, running_world  # noqa: F401

pytestmark = [pytest.mark.perf, pytest.mark.integration]

TARGET_MS = {"view": 200, "chunks": 500, "citizens": 100, "citizen": 100, "companies": 100, "summary": 100}


def test_report_read_api_p95_with_runner_x16(live_client, running_world):
    b = f"/api/v1/worlds/{running_world}"
    cid = live_client.get(f"{b}/citizens?limit=1").json()["items"][0]["id"]
    calls = {
        "view": f"{b}/view",
        "chunks": f"{b}/chunks",
        "citizens": f"{b}/citizens?limit=100",
        "citizen": f"{b}/citizens/{cid}",
        "companies": f"{b}/companies",
        "summary": f"{b}/summary",
    }
    rows = []
    for name, url in calls.items():
        ms = []
        for _ in range(50):
            t0 = time.perf_counter()
            r = live_client.get(url)
            ms.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 200
        ms.sort()
        rows.append((name, statistics.median(ms), ms[int(0.95 * len(ms)) - 1], ms[-1]))
    print("\nendpoint     p50ms   p95ms   maxms  target(p95)")
    for name, p50, p95, mx in rows:
        flag = "" if p95 <= TARGET_MS[name] else "  OVER"
        print(f"{name:<10} {p50:7.1f} {p95:7.1f} {mx:7.1f}  {TARGET_MS[name]}{flag}")
