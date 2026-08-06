import logging
import time
from typing import Any

from playwright.sync_api import (
    BrowserContext,
    Page,
    sync_playwright,
)

from cgv_api import CgvApiClient
from config import (
    BOOKING_PAGE_URL,
    BROWSER_REFRESH_INTERVAL_SEC,
    CO_CD,
    DISCORD_WEBHOOK_URL,
    LOG_FILE,
    POLL_INTERVAL_SEC,
    STATE_FILE,
    USER_AGENT,
)
from targets_store import load_targets
from utils import (
    build_signature,
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


def open_booking_page(page: Page) -> None:
    page.goto(
        BOOKING_PAGE_URL,
        timeout=30_000,
        wait_until="networkidle",
    )


def reload_booking_page(page: Page) -> None:
    page.reload(
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


def check_target(
    api: CgvApiClient,
    target: dict[str, Any],
    state: dict[str, set[str]],
    first_run: bool,
) -> None:
    target_id = str(target["id"])
    site_no = str(target["site_no"])
    site_name = str(target["site_name"])
    grades = {str(grade) for grade in target["grades"]}
    movie_filter = str(target.get("movie") or "")
    date_filter = str(target.get("date") or "")

    # 새로 추가된(state에 아직 없는) 대상은 이번 폴링을 기준선으로만 저장하고
    # 알림은 보내지 않는다 (첫 실행 때 first_run과 동일한 취급).
    target_is_new = target_id not in state
    previous_signatures = state.get(
        target_id,
        set(),
    )

    current_signatures: set[str] = set()
    new_entries: list[dict[str, Any]] = []

    scheduled_dates = api.fetch_scheduled_dates(
        site_no,
    )

    for scn_ymd in scheduled_dates:
        if date_filter and str(scn_ymd) != date_filter:
            continue

        entries = api.fetch_showtimes(
            site_no=site_no,
            scn_ymd=scn_ymd,
        )

        for entry in entries:
            entry_site_no = str(entry.get("siteNo", ""))

            if entry_site_no != site_no:
                continue

            grade = str(entry.get("tcscnsGradNm", ""))

            if grades and grade not in grades:
                continue

            if movie_filter and movie_filter not in str(entry.get("prodNm", "")):
                continue

            signature = build_signature(entry)
            current_signatures.add(signature)

            is_new = not first_run and not target_is_new and signature not in previous_signatures

            if is_new:
                new_entries.append(entry)

        time.sleep(0.3)

    if new_entries:
        new_entries.sort(
            key=lambda entry: (
                str(entry.get("scnYmd", "")),
                str(entry.get("scnsrtTm", "")),
            )
        )

        log_info(f"{site_name} new showtimes: {len(new_entries)}")

        message = build_notification_message(
            site_name=site_name,
            entries=new_entries,
        )

        send_discord(
            webhook_url=DISCORD_WEBHOOK_URL,
            content=message,
        )

    state[target_id] = current_signatures


def recover_browser_session(
    page: Page,
) -> bool:
    try:
        reload_booking_page(page)
        log_info("browser session recovered")
        return True

    except Exception as error:
        log_exception(f"browser recovery failed: {error}")
        return False


def run_monitor(
    context: BrowserContext,
    page: Page,
) -> None:
    state = load_state(STATE_FILE)
    first_run = not state

    api = CgvApiClient(
        request=context.request,
        co_cd=CO_CD,
    )

    open_booking_page(page)

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
                reload_booking_page(page)
                last_refresh = time.monotonic()

                log_info("browser session refreshed")

            targets = load_targets()

            # 봇으로 제거된 대상의 state는 지운다. 나중에 같은 극장을 다시
            # 추가하면 옛 기록과 비교하지 않고 새로 기준선을 잡게 하기 위함.
            live_target_ids = {str(target["id"]) for target in targets}
            state = {
                target_id: signatures
                for target_id, signatures in state.items()
                if target_id in live_target_ids
            }

            for target in targets:
                check_target(
                    api=api,
                    target=target,
                    state=state,
                    first_run=first_run,
                )

            save_state(
                state_file=STATE_FILE,
                state=state,
            )

            first_run = False

        except Exception as error:
            log_exception(f"poll failed, will retry: {error}")

            recovered = recover_browser_session(page)

            if recovered:
                last_refresh = time.monotonic()

        time.sleep(POLL_INTERVAL_SEC)


def run() -> None:
    base_url = get_base_url(BOOKING_PAGE_URL)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            base_url=base_url,
        )

        page = context.new_page()

        try:
            run_monitor(
                context=context,
                page=page,
            )

        except KeyboardInterrupt:
            log_info("cgv-monitor stopped by user")

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
