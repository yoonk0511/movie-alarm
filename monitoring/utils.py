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
