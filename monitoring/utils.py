import json
import os
from dataclasses import asdict
from typing import Any, TypeVar

from cgv_open_push.cgv_models import CgvShowtime
from logging_setup import log_error

T = TypeVar("T")


def _read_json(file: str, default: Any) -> Any:
    if not os.path.exists(file):
        return default

    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        log_error(f"failed to load {file}: {error}")
        return default


def atomic_write_json(file: str, data: Any) -> None:
    temporary_file = f"{file}.tmp"

    try:
        with open(temporary_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temporary_file, file)
    except OSError as error:
        log_error(f"failed to save {file}: {error}")
        try:
            if os.path.exists(temporary_file):
                os.remove(temporary_file)
        except OSError:
            pass


def load_state(state_file: str) -> dict[str, set[str]]:
    data = _read_json(state_file, {})
    if not isinstance(data, dict):
        log_error("invalid state file format")
        return {}

    return {
        str(site_no): {str(signature) for signature in signatures}
        for site_no, signatures in data.items()
        if isinstance(signatures, list)
    }


def save_state(state_file: str, state: dict[str, set[str]]) -> None:
    serialized_state = {site_no: sorted(signatures) for site_no, signatures in state.items()}
    atomic_write_json(state_file, serialized_state)


def build_signature(entry: CgvShowtime) -> str:
    return "|".join(
        str(field)
        for field in (entry.provider, entry.date, entry.site_no, entry.screen, entry.time, entry.movie)
    )


def load_showtimes(showtimes_file: str) -> list[CgvShowtime]:
    """fetch.py가 쓴 정규화된 회차 스냅샷을 읽는다. fetch가 아직 한 번도 안
    돌았거나 파일이 깨졌으면 빈 리스트 — match는 다음 폴링에 다시 시도한다."""
    if not os.path.exists(showtimes_file):
        return []

    data = _read_json(showtimes_file, {})
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        log_error("invalid showtimes file format")
        return []

    return [CgvShowtime(**entry) for entry in entries if isinstance(entry, dict)]


def save_showtimes(
    showtimes_file: str,
    entries: list[CgvShowtime],
    fetched_at: str,
) -> None:
    atomic_write_json(
        showtimes_file,
        {"fetched_at": fetched_at, "entries": [asdict(entry) for entry in entries]},
    )


def load_json_list(file: str, cls: type[T]) -> list[T]:
    """통째로 교체되는 dataclass 리스트 캐시 파일을 읽는다 (극장/영화 목록 등).
    fetch.py가 아직 한 번도 안 돌았거나 파일이 깨졌으면 빈 리스트."""
    data = _read_json(file, [])
    if not isinstance(data, list):
        log_error(f"invalid list format in {file}")
        return []

    return [cls(**item) for item in data if isinstance(item, dict)]


def save_json_list(file: str, items: list[T]) -> None:
    atomic_write_json(file, [asdict(item) for item in items])


def format_time(hhmm: str) -> str:
    if len(hhmm) < 4:
        return hhmm

    return f"{hhmm[:2]}:{hhmm[2:4]}"


def format_date(yyyymmdd: str) -> str:
    if len(yyyymmdd) != 8:
        return yyyymmdd

    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
