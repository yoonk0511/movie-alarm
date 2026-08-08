from contextlib import asynccontextmanager

from playwright.async_api import async_playwright

from cgv_open_push.config import BOOKING_PAGE_URL, USER_AGENT


@asynccontextmanager
async def cgv_browser_session():
    async with async_playwright() as p:
        # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다
        # (cgv_open_push/cgv_api.py 참고).
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        page = await context.new_page()
        await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")
        try:
            yield page
        finally:
            await browser.close()
