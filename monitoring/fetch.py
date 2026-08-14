import asyncio
import time
from dataclasses import asdict
from datetime import datetime, timezone

from playwright.async_api import Page, async_playwright

from alarm_bot.config import DISCORD_WEBHOOK_URL
from alarm_bot.notify import send_discord
from alarm_bot.targets_store import load_targets
from cgv_open_push.cgv_api import CgvTheaterClient
from cgv_open_push.cgv_models import CgvShowtime
from cgv_open_push.config import BOOKING_PAGE_URL, USER_AGENT
from logging_setup import configure, log_exception, log_info

from .config import BROWSER_REFRESH_INTERVAL_SEC, POLL_INTERVAL_SEC, SHOWTIMES_FILE
from .utils import save_showtimes

configure()


def target_site_names() -> list[str]:
    """지금 감시 중인 target들이 걸려있는 극장 이름만 뽑는다 — 아무도 안 보는
    극장까지 매번 긁을 필요는 없다."""
    return sorted({str(t["site_name"]) for t in load_targets()})


async def fetch_all_showtimes(page: Page) -> list[dict]:
    """target이 걸린 극장마다 스케줄된 날짜 전부의 회차를 가져와 정규화한다.
    극장 하나를 못 찾는 등 개별 실패는 그 극장만 건너뛰고 나머지는 계속한다."""
    all_entries: list[dict] = []

    for site_name in target_site_names():
        theater = CgvTheaterClient(page, site_name=site_name)
        try:
            scheduled_dates = await theater.fetch_scheduled_dates()
        except Exception as error:
            log_exception(f"{site_name} fetch_scheduled_dates failed, skipping: {error}")
            continue

        for scn_ymd in scheduled_dates:
            try:
                raw_entries = await theater.fetch_showtimes(scn_ymd)
            except Exception as error:
                log_exception(f"{site_name} {scn_ymd} fetch_showtimes failed, skipping: {error}")
                continue

            all_entries.extend(
                asdict(CgvShowtime.from_api(raw, site_name=site_name)) for raw in raw_entries
            )

            await asyncio.sleep(0.3)

    return all_entries


async def open_booking_page(page: Page) -> None:
    await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")


async def reload_booking_page(page: Page) -> None:
    await page.reload(timeout=30_000, wait_until="networkidle")


async def recover_browser_session(page: Page) -> bool:
    try:
        await reload_booking_page(page)
        log_info("browser session recovered")
        return True
    except Exception as error:
        log_exception(f"browser recovery failed: {error}")
        return False


async def run_fetch_loop(page: Page) -> None:
    await open_booking_page(page)

    log_info("cgv-fetcher started, browser session established")
    send_discord(webhook_url=DISCORD_WEBHOOK_URL, content="cgv-fetcher started...")

    last_refresh = time.monotonic()

    while True:
        try:
            elapsed = time.monotonic() - last_refresh
            if elapsed >= BROWSER_REFRESH_INTERVAL_SEC:
                await reload_booking_page(page)
                last_refresh = time.monotonic()
                log_info("browser session refreshed")

            entries = await fetch_all_showtimes(page)
            save_showtimes(
                SHOWTIMES_FILE,
                entries,
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            log_info(f"fetched {len(entries)} showtimes")

        except Exception as error:
            log_exception(f"fetch poll failed, will retry: {error}")

            recovered = await recover_browser_session(page)
            if recovered:
                last_refresh = time.monotonic()

        await asyncio.sleep(POLL_INTERVAL_SEC)


async def run() -> None:
    async with async_playwright() as playwright:
        # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다
        # (일반 브라우저는 안 막히는 것 확인함). EC2 등 화면 없는 서버에 배포할 땐
        # Xvfb 같은 가상 디스플레이 없이는 이 프로세스가 바로 실패한다.
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        page = await context.new_page()

        try:
            await run_fetch_loop(page)
        except KeyboardInterrupt:
            log_info("cgv-fetcher stopped by user")
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
