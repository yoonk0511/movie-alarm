import asyncio
import logging
import time
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Page,
    async_playwright,
)

from cgv_api import CgvTheaterClient
from config import (
    BOOKING_PAGE_URL,
    BROWSER_REFRESH_INTERVAL_SEC,
    DISCORD_WEBHOOK_URL,
    LOG_FILE,
    POLL_INTERVAL_SEC,
    STATE_FILE,
    USER_AGENT,
)
from monitor import check_target
from targets_store import load_targets
from utils import (
    format_date,
    format_time,
    get_base_url,
    load_state,
    log_exception,
    log_info,
    save_state,
    send_discord,
)

logging.basicConfig(
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        )
    ],
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)


async def open_booking_page(page: Page) -> None:
    await page.goto(
        BOOKING_PAGE_URL,
        timeout=30_000,
        wait_until="networkidle",
    )


async def reload_booking_page(page: Page) -> None:
    await page.reload(
        timeout=30_000,
        wait_until="networkidle",
    )


def build_notification_message(
    site_name: str,
    entries: list[dict[str, Any]],
) -> str:
    lines = [
        f"**{site_name} 예매 오픈 알림**",
    ]

    for entry in entries:
        scn_ymd = str(entry.get("scnYmd", ""))
        start_time = str(entry.get("scnsrtTm", ""))
        grade = str(entry.get("tcscnsGradNm", ""))
        product_name = str(entry.get("prodNm", ""))
        screen_name = str(entry.get("scnsNm", ""))

        lines.append(
            f"- {format_date(scn_ymd)} "
            f"{format_time(start_time)} "
            f"[{grade}] "
            f"{product_name} "
            f"({screen_name})"
        )

    lines.append(BOOKING_PAGE_URL)

    return "\n".join(lines)


async def recover_browser_session(
    page: Page,
) -> bool:
    try:
        await reload_booking_page(page)
        log_info("browser session recovered")
        return True

    except Exception as error:
        log_exception(f"browser recovery failed: {error}")
        return False


async def run_monitor(
    context: BrowserContext,
    page: Page,
) -> None:
    state = load_state(STATE_FILE)
    first_run = not state

    # site_name별로 CgvTheaterClient를 재사용한다 — 매번 새로 만들면 _resolve_site_no가
    # 폴링마다 fetch_regn_list()를 다시 호출해서 극장 177개를 매번 긁어오게 된다.
    theater_clients: dict[str, CgvTheaterClient] = {}

    await open_booking_page(page)

    log_info("cgv-monitor started, browser session established")

    send_discord(
        webhook_url=DISCORD_WEBHOOK_URL,
        content="cgv-monitor started...",
    )

    last_refresh = time.monotonic()

    while True:
        try:
            elapsed = time.monotonic() - last_refresh

            if elapsed >= BROWSER_REFRESH_INTERVAL_SEC:
                await reload_booking_page(page)
                last_refresh = time.monotonic()

                log_info("browser session refreshed")

            targets = load_targets()

            # 봇으로 제거된 대상의 state/클라이언트는 지운다. 나중에 같은 극장을 다시
            # 추가하면 옛 기록과 비교하지 않고 새로 기준선을 잡게 하기 위함.
            live_target_ids = {str(target["id"]) for target in targets}
            state = {
                target_id: signatures
                for target_id, signatures in state.items()
                if target_id in live_target_ids
            }
            theater_clients = {
                target_id: client
                for target_id, client in theater_clients.items()
                if target_id in live_target_ids
            }

            for target in targets:
                target_id = str(target["id"])

                theater = theater_clients.get(target_id)
                if theater is None:
                    theater = CgvTheaterClient(context.request, site_name=target["site_name"])
                    theater_clients[target_id] = theater

                new_entries = await check_target(
                    theater=theater,
                    target=target,
                    state=state,
                    first_run=first_run,
                )

                if new_entries:
                    message = build_notification_message(
                        site_name=target["site_name"],
                        entries=new_entries,
                    )
                    send_discord(
                        webhook_url=DISCORD_WEBHOOK_URL,
                        content=message,
                    )

            save_state(
                state_file=STATE_FILE,
                state=state,
            )

            first_run = False

        except Exception as error:
            log_exception(f"poll failed, will retry: {error}")

            recovered = await recover_browser_session(page)

            if recovered:
                last_refresh = time.monotonic()

        await asyncio.sleep(POLL_INTERVAL_SEC)


async def run() -> None:
    base_url = get_base_url(BOOKING_PAGE_URL)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
        )

        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            base_url=base_url,
        )

        page = await context.new_page()

        try:
            await run_monitor(
                context=context,
                page=page,
            )

        except KeyboardInterrupt:
            log_info("cgv-monitor stopped by user")

        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
