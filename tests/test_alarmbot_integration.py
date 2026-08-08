import asyncio
import os

import pytest

from alarm_bot.bot import search_theaters

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="실제 CGV 사이트에 접속하는 통합 테스트. RUN_NETWORK_TESTS=1 로 실행",
)


def test_search_theaters_returns_matches():
    matches = asyncio.run(search_theaters("용산"))
    site_nos = {m["site_no"] for m in matches}
    assert "0013" in site_nos
