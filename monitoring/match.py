import os
import time

from alarm_bot.config import DISCORD_WEBHOOK_URL
from alarm_bot.notify import send_discord
from alarm_bot.targets_store import TargetSpec, load_targets
from cgv_open_push.cgv_models import CgvShowtime
from cgv_open_push.config import BOOKING_PAGE_URL
from logging_setup import configure, log_exception, log_info

from .config import POLL_INTERVAL_SEC, SHOWTIMES_FILE, STATE_FILE
from .monitor import TargetRegistry
from .utils import format_date, format_time, load_showtimes, load_state, save_state

configure()


def build_notification_message(
    site_name: str,
    entries: list[CgvShowtime],
) -> str:
    lines = [f"**{site_name} 예매 오픈 알림**"]

    for entry in entries:
        lines.append(
            f"- {format_date(entry.date)} {format_time(entry.time)} "
            f"[{entry.grade or ''}] {entry.movie} ({entry.screen or ''})"
        )

    lines.append(BOOKING_PAGE_URL)

    return "\n".join(lines)


def check_all_targets(
    registry: TargetRegistry,
    targets: list[TargetSpec],
    entries: list[CgvShowtime],
    first_run: bool,
) -> None:
    """targets.json에서 나온 감시 대상들을 최신 목록과 동기화하고, 각 Target이
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
        try:
            if not os.path.exists(SHOWTIMES_FILE):
                # fetch.py가 아직 한 번도 스냅샷을 안 썼다 — 여기서 빈 스냅샷으로
                # baseline을 잡으면(첫 실행이든 재시작 중이든) 나중에 진짜
                # 스냅샷이 들어왔을 때 이미 열려있던 회차가 전부 "새 회차"로
                # 보여서 알림이 중복 발사된다. fetch가 쓸 때까지 그냥 기다린다.
                log_info("showtimes snapshot not ready yet, waiting for cgv-fetcher")
            else:
                entries = load_showtimes(SHOWTIMES_FILE)

                check_all_targets(
                    registry=registry,
                    targets=load_targets(),
                    entries=entries,
                    first_run=first_run,
                )

                save_state(state_file=STATE_FILE, state=registry.signatures_snapshot())
                first_run = False
        except Exception as error:
            log_exception(f"match poll failed, will retry: {error}")

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log_info("cgv-matcher stopped by user")
