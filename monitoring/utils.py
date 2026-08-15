import json
import os
from typing import Any

from logging_setup import log_error


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
        "provider",
        "date",
        "site_no",
        "screen",
        "time",
        "movie",
    )

    return "|".join(str(entry.get(field, "")) for field in fields)


def load_showtimes(
    showtimes_file: str,
) -> list[dict[str, Any]]:
    """fetch.py가 쓴 정규화된 회차 스냅샷을 읽는다. fetch가 아직 한 번도 안
    돌았거나 파일이 깨졌으면 빈 리스트 — match는 다음 폴링에 다시 시도한다."""
    if not os.path.exists(showtimes_file):
        return []

    try:
        with open(showtimes_file, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"failed to load showtimes file: {error}")
        return []

    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        log_error("invalid showtimes file format")
        return []

    return [entry for entry in entries if isinstance(entry, dict)]


def save_showtimes(
    showtimes_file: str,
    entries: list[dict[str, Any]],
    fetched_at: str,
) -> None:
    temporary_file = f"{showtimes_file}.tmp"

    try:
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(
                {"fetched_at": fetched_at, "entries": entries},
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temporary_file, showtimes_file)

    except OSError as error:
        log_error(f"failed to save showtimes file: {error}")

        try:
            if os.path.exists(temporary_file):
                os.remove(temporary_file)
        except OSError:
            pass


def load_theaters(
    theaters_file: str,
) -> list[dict[str, Any]]:
    """fetch.py가 하루 한 번 갱신하는 극장 목록 캐시를 읽는다. 아직 한 번도 안
    돌았거나 파일이 깨졌으면 빈 리스트."""
    if not os.path.exists(theaters_file):
        return []

    try:
        with open(theaters_file, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"failed to load theaters file: {error}")
        return []

    if not isinstance(data, list):
        log_error("invalid theaters file format")
        return []

    return [theater for theater in data if isinstance(theater, dict)]


def save_theaters(
    theaters_file: str,
    theaters: list[dict[str, Any]],
) -> None:
    temporary_file = f"{theaters_file}.tmp"

    try:
        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(theaters, file, ensure_ascii=False, indent=2)

        os.replace(temporary_file, theaters_file)

    except OSError as error:
        log_error(f"failed to save theaters file: {error}")

        try:
            if os.path.exists(temporary_file):
                os.remove(temporary_file)
        except OSError:
            pass


def format_time(hhmm: str) -> str:
    if len(hhmm) < 4:
        return hhmm

    return f"{hhmm[:2]}:{hhmm[2:4]}"


def format_date(yyyymmdd: str) -> str:
    if len(yyyymmdd) != 8:
        return yyyymmdd

    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
