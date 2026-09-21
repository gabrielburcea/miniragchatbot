import asyncio
import time

from app.llm.tools import get_employee_context


def test_get_employee_context_runs_in_parallel():
    """Total time must be ~1s (concurrent), not ~3s (sequential)."""
    start = time.perf_counter()
    result = asyncio.run(get_employee_context("emp-001"))
    elapsed = time.perf_counter() - start

    # Generous upper bound to avoid flaky CI failures, but well under 3s
    assert elapsed < 1.5

    assert result == {
        "name": "Jane Doe",
        "grade": "Senior",
        "manager": "John Smith",
        "team_size": 8,
        "team_name": "Platform",
    }