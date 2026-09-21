"""
Mock employee-data tool the LLM can invoke: get_employee_context(user_id).

README requirement: fetch profile, manager info, and team info concurrently
so total latency is ~1s (one sleep), not ~3s (three sequential sleeps).
Each sub-fetch is faked with asyncio.sleep(1) to simulate a slow API call.
"""

import asyncio


async def _fetch_profile(user_id: str) -> dict:
    """Simulates a slow profile lookup."""
    await asyncio.sleep(1)
    return {"name": "Jane Doe", "grade": "Senior"}


async def _fetch_manager_info(user_id: str) -> dict:
    """Simulates a slow manager lookup."""
    await asyncio.sleep(1)
    return {"manager": "John Smith"}


async def _fetch_team_info(user_id: str) -> dict:
    """Simulates a slow team lookup."""
    await asyncio.sleep(1)
    return {"team_size": 8, "team_name": "Platform"}


async def get_employee_context(user_id: str) -> dict:
    """
    Runs all three lookups concurrently via asyncio.gather, so the total
    wait is bounded by the slowest single call (~1s) instead of their sum (~3s).
    """
    profile, manager_info, team_info = await asyncio.gather(
        _fetch_profile(user_id),
        _fetch_manager_info(user_id),
        _fetch_team_info(user_id),
    )
    return {**profile, **manager_info, **team_info}