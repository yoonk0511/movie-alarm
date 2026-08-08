import asyncio
from unittest.mock import AsyncMock, MagicMock


def run(coro):
    return asyncio.run(coro)


def make_interaction():
    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def make_target(**overrides):
    target = {
        "id": "0013",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": [],
        "grades": ["아이맥스", "4DX"],
    }
    target.update(overrides)
    return target
