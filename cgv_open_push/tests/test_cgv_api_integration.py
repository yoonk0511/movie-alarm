import asyncio
import os

import pytest
from playwright.async_api import async_playwright

from cgv_open_push.cgv_api import CgvApiClient, CgvTheaterClient
from cgv_open_push.config import BOOKING_PAGE_URL

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="실제 CGV 사이트에 접속하는 통합 테스트 (WAF의 403 차단 여부 확인). "
    "RUN_NETWORK_TESTS=1 로 실행",
)

SAMPLE_THEATER_NAME = "용산아이파크몰"


def run(coro):
    return asyncio.run(coro)


def test_cgv_api_does_not_hit_403():
    # CgvApiError는 403을 포함한 비정상 응답에서 발생한다 — 아래가 예외 없이
    # 끝나면 WAF가 이 요청 패턴(page.evaluate 안에서 fetch)을 막지 않는다는 뜻.
    async def check() -> None:
        async with async_playwright() as playwright:
            # headless=True는 CGV WAF에 403으로 차단된다 — cgv_api.py 참고.
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")

            try:
                client = CgvApiClient(page)
                theaters = await client.fetch_regn_list()
                assert len(theaters) > 0

                movies = await client.fetch_movie_list()
                assert len(movies) > 0

                theater_client = CgvTheaterClient(page, site_name=SAMPLE_THEATER_NAME)
                dates = await theater_client.fetch_scheduled_dates()
                assert isinstance(dates, list)

                entries = await theater_client.fetch_showtime_entries()
                assert isinstance(entries, list)
            finally:
                await browser.close()

    run(check())
