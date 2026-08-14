import time
from typing import Any

from alarm_bot.config import DISCORD_WEBHOOK_URL
from alarm_bot.notify import send_discord
from alarm_bot.targets_store import load_targets
from cgv_open_push.config import BOOKING_PAGE_URL
from logging_setup import configure, log_exception, log_info

from .config import POLL_INTERVAL_SEC, SHOWTIMES_FILE, STATE_FILE
from .monitor import TargetRegistry
from .utils import format_date, format_time, load_showtimes, load_state, save_state

configure()


def build_notification_message(
    site_name: str,
    entries: list[dict[str, Any]],
) -> str:
    lines = [f"**{site_name} 예매 오픈 알림**"]

    for entry in entries:
        lines.append(
            f"- {format_date(str(entry.get('date', '')))} "
            f"{format_time(str(entry.get('time', '')))} "
            f"[{entry.get('grade', '')}] "
            f"{entry.get('movie', '')} "
            f"({entry.get('screen', '')})"
        )

    lines.append(BOOKING_PAGE_URL)

    return "\n".join(lines)


def check_all_targets(
    registry: TargetRegistry,
    targets: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    first_run: bool,
) -> None:
    """targets.json에서 나온 감시 대상 dict들을 최신 목록과 동기화하고, 각 Target이
    스스로 판단한 새 회차가 있으면 Discord로 알린다. 대상 하나에서 에러가 나도
    그 대상만 건너뛰고 나머지는 계속 진행한다."""
    for target, is_new in registry.sync(targets):
        try:
            new_entries = target.check(entries, baseline_only=first_run or is_new)
        except Exception as error:
            log_exception(f"{target.site_name} check failed, skipping this poll: {error}")
            continue

        if new_entries:
            message = build_notification_message(
                site_name=target.site_name,
                entries=new_entries,
            )
            send_discord(webhook_url=DISCORD_WEBHOOK_URL, content=message)


def run() -> None:
    state = load_state(STATE_FILE)
    first_run = not state

    registry = TargetRegistry()
    registry.sync(load_targets())
    registry.restore_signatures(state)

    log_info("cgv-matcher started")

    while True:
        entries = load_showtimes(SHOWTIMES_FILE)

        check_all_targets(
            registry=registry,
            targets=load_targets(),
            entries=entries,
            first_run=first_run,
        )

        save_state(state_file=STATE_FILE, state=registry.signatures_snapshot())
        first_run = False

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log_info("cgv-matcher stopped by user")
