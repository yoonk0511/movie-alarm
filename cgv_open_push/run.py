import asyncio
import logging
import time
from typing import Any

from playwright.async_api import (
    Page,
    async_playwright,
)

from .config import (
    BOOKING_PAGE_URL,
    BROWSER_REFRESH_INTERVAL_SEC,
    DISCORD_WEBHOOK_URL,
    LOG_FILE,
    POLL_INTERVAL_SEC,
    STATE_FILE,
    USER_AGENT,
)
from .monitor import TargetRegistry
from .targets_store import load_targets
from .utils import (
    format_date,
    format_time,
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


async def check_all_targets(
    registry: TargetRegistry,
    targets: list[dict[str, Any]],
    first_run: bool,
) -> None:
    """targets.json에서 나온 감시 대상 dict들을 최신 목록과 동기화하고, 각 Target이
    스스로 판단한 새 회차가 있으면 Discord로 알린다. 극장 하나를 못 찾는 등 개별
    대상에서 에러가 나도 그 대상만 이번 폴링을 건너뛰고, 다른 대상은 계속 진행한다."""
    for target, is_new in registry.sync(targets):
        try:
            new_entries = await target.check(baseline_only=first_run or is_new)
        except Exception as error:
            log_exception(f"{target.site_name} check failed, skipping this poll: {error}")
            continue

        if new_entries:
            message = build_notification_message(
                site_name=target.site_name,
                entries=new_entries,
            )
            send_discord(
                webhook_url=DISCORD_WEBHOOK_URL,
                content=message,
            )


async def run_monitor(
    page: Page,
) -> None:
    state = load_state(STATE_FILE)
    first_run = not state

    registry = TargetRegistry(page)
    # 시작할 때 한 번 동기화해서 Target들을 만든 다음 저장된 signature를 복원한다.
    # 이후 폴링에서는 registry가 같은 Target 인스턴스를 재사용하므로(site_no 캐시,
    # 누적된 signature 유지), 다시 복원할 필요가 없다.
    registry.sync(load_targets())
    registry.restore_signatures(state)

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

            await check_all_targets(
                registry=registry,
                targets=load_targets(),
                first_run=first_run,
            )

            save_state(
                state_file=STATE_FILE,
                state=registry.signatures_snapshot(),
            )

            first_run = False

        except Exception as error:
            log_exception(f"poll failed, will retry: {error}")

            recovered = await recover_browser_session(page)

            if recovered:
                last_refresh = time.monotonic()

        await asyncio.sleep(POLL_INTERVAL_SEC)


async def run() -> None:
    async with async_playwright() as playwright:
        # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다
        # (일반 브라우저는 안 막히는 것 확인함). EC2 등 화면 없는 서버에 배포할 땐
        # Xvfb 같은 가상 디스플레이 없이는 이 프로세스가 바로 실패한다 — 아직 EC2엔
        # 반영 안 함, systemd로 배포하기 전에 Xvfb부터 준비할 것.
        browser = await playwright.chromium.launch(
            headless=False,
        )

        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
        )

        page = await context.new_page()

        try:
            await run_monitor(page=page)

        except KeyboardInterrupt:
            log_info("cgv-monitor stopped by user")

        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
