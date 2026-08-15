import asyncio
import time
from datetime import datetime, timezone

from playwright.async_api import Page, async_playwright

from alarm_bot.config import DISCORD_WEBHOOK_URL
from alarm_bot.notify import send_discord
from alarm_bot.targets_store import load_targets
from cgv_open_push.cgv_api import CgvApiClient, CgvTheaterClient
from cgv_open_push.cgv_models import CgvShowtime
from cgv_open_push.config import BOOKING_PAGE_URL, USER_AGENT
from logging_setup import configure, log_exception, log_info

from .config import (
    BROWSER_REFRESH_INTERVAL_SEC,
    CATALOG_REFRESH_INTERVAL_SEC,
    MOVIES_FILE,
    POLL_INTERVAL_SEC,
    SHOWTIMES_FILE,
    THEATERS_FILE,
)
from .utils import save_json_list, save_showtimes

configure()


def target_site_names() -> list[str]:
    """지금 감시 중인 target들이 걸려있는 극장 이름만 뽑는다. CGV 전국 극장을 다
    긁는 건 실측해보니 한 바퀴에 30분~3시간이 걸려서 5분 주기(POLL_INTERVAL_SEC)와
    안 맞았다 — target 걸린 몇 개만 긁는 게 실제로 돌아가는 유일한 방법."""
    return sorted({t.site_name for t in load_targets()})


async def fetch_all_showtimes(
    page: Page,
    theater_clients: dict[str, CgvTheaterClient],
) -> list[CgvShowtime]:
    """target이 걸린 극장마다 스케줄된 날짜 전부의 회차를 가져와 정규화한다.
    극장 하나를 못 찾는 등 개별 실패는 그 극장만 건너뛰고 나머지는 계속한다.

    theater_clients는 호출부(run_fetch_loop)가 폴링 사이에 들고 있는 캐시다 —
    CgvTheaterClient는 첫 호출 때 site_no를 찾아서 인스턴스에 캐싱해두는데, 매
    폴링마다 새로 만들면 그 캐시가 매번 버려져서 극장마다 site_no 조회가
    반복된다. site_no는 브라우저 세션(쿠키)과 무관해서 페이지가 새로고침돼도
    안 깨진다."""
    all_entries: list[CgvShowtime] = []
    live_site_names = target_site_names()

    for site_name in list(theater_clients):
        if site_name not in live_site_names:
            del theater_clients[site_name]

    for site_name in live_site_names:
        if site_name not in theater_clients:
            theater_clients[site_name] = CgvTheaterClient(page, site_name=site_name)
        theater = theater_clients[site_name]
        try:
            scheduled_dates = await theater.fetch_scheduled_dates()
        except Exception as error:
            log_exception(f"{site_name} fetch_scheduled_dates failed, skipping: {error}")
            continue

        for scn_ymd in scheduled_dates:
            try:
                showtimes = await theater.fetch_showtimes(scn_ymd)
            except Exception as error:
                log_exception(f"{site_name} {scn_ymd} fetch_showtimes failed, skipping: {error}")
                continue

            all_entries.extend(showtimes)

            await asyncio.sleep(0.3)

    return all_entries


async def refresh_catalog_cache(page: Page) -> None:
    """bot의 /search, /add가 매번 브라우저를 새로 안 띄우고 즉시 응답(자동완성
    포함)할 수 있도록 극장 목록과 전체 상영작 목록을 캐시한다. showtimes와 달리
    둘 다 거의 안 바뀌니 이 함수는 CATALOG_REFRESH_INTERVAL_SEC 주기로만 불린다."""
    client = CgvApiClient(page)

    theaters = await client.fetch_regn_list()
    save_json_list(THEATERS_FILE, theaters)

    movies = await client.fetch_movie_list()
    save_json_list(MOVIES_FILE, movies)

    log_info(f"refreshed catalog cache (극장 {len(theaters)}개, 영화 {len(movies)}개)")


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
    await refresh_catalog_cache(page)

    log_info("cgv-fetcher started, browser session established")
    send_discord(webhook_url=DISCORD_WEBHOOK_URL, content="cgv-fetcher started...")

    theater_clients: dict[str, CgvTheaterClient] = {}
    last_refresh = time.monotonic()
    last_catalog_refresh = time.monotonic()

    while True:
        try:
            elapsed = time.monotonic() - last_refresh
            if elapsed >= BROWSER_REFRESH_INTERVAL_SEC:
                await reload_booking_page(page)
                last_refresh = time.monotonic()
                log_info("browser session refreshed")

            if time.monotonic() - last_catalog_refresh >= CATALOG_REFRESH_INTERVAL_SEC:
                await refresh_catalog_cache(page)
                last_catalog_refresh = time.monotonic()

            entries = await fetch_all_showtimes(page, theater_clients)
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
