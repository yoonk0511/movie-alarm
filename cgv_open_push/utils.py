import json
import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import requests


def get_base_url(url: str) -> str:
    parsed = urlsplit(url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid BOOKING_PAGE_URL: {url}")

    return f"{parsed.scheme}://{parsed.netloc}"


def log_info(message: str) -> None:
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}",
        flush=True,
    )
    logging.info(message)


def log_error(message: str) -> None:
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {message}",
        flush=True,
    )
    logging.error(message)


def log_exception(message: str) -> None:
    """except 블록 안에서만 호출: 콘솔에는 메시지만 찍고, 로그 파일에는 트레이스백까지 남긴다.
    운영 중 원인 불명 에러가 나면 메시지만으로는 어디서 터졌는지 알 수 없어서, 실제
    예외 상황(재시도 경로)에서는 log_error 대신 이걸 쓴다."""
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {message}",
        flush=True,
    )
    logging.exception(message)


def send_discord(webhook_url: str, content: str) -> None:
    if not webhook_url:
        log_error("DISCORD_WEBHOOK_URL not set, skipping notification")
        return

    try:
        response = requests.post(
            webhook_url,
            json={"content": content},
            timeout=10,
        )
        response.raise_for_status()

    except requests.RequestException as error:
        log_error(f"failed to send discord message: {error}")


def load_state(
    state_file: str,
) -> dict[str, set[str]]:
    if not os.path.exists(state_file):
        return {}

    try:
        with open(
            state_file,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except (OSError, json.JSONDecodeError) as error:
        log_error(f"failed to load state file: {error}")
        return {}

    if not isinstance(data, dict):
        log_error("invalid state file format")
        return {}

    state: dict[str, set[str]] = {}

    for site_no, signatures in data.items():
        if not isinstance(signatures, list):
            continue

        state[str(site_no)] = {str(signature) for signature in signatures}

    return state


def save_state(
    state_file: str,
    state: dict[str, set[str]],
) -> None:
    serialized_state = {site_no: sorted(signatures) for site_no, signatures in state.items()}

    temporary_file = f"{state_file}.tmp"

    try:
        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                serialized_state,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_file,
            state_file,
        )

    except OSError as error:
        log_error(f"failed to save state file: {error}")

        try:
            if os.path.exists(temporary_file):
                os.remove(temporary_file)
        except OSError:
            pass


def build_signature(
    entry: dict[str, Any],
) -> str:
    fields = (
        "scnYmd",
        "siteNo",
        "scnsNm",
        "scnsrtTm",
        "prodNm",
    )

    return "|".join(str(entry.get(field, "")) for field in fields)


def format_time(hhmm: str) -> str:
    if len(hhmm) < 4:
        return hhmm

    return f"{hhmm[:2]}:{hhmm[2:4]}"


def format_date(yyyymmdd: str) -> str:
    if len(yyyymmdd) != 8:
        return yyyymmdd

    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
