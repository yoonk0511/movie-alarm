from unittest.mock import MagicMock

import monitoring.utils as monitoring_utils
from cgv_open_push.cgv_models import CgvShowtime, CgvTheater
from monitoring.utils import (
    build_signature,
    format_date,
    format_time,
    load_json_list,
    load_showtimes,
    save_json_list,
    save_showtimes,
)


def test_format_time_inserts_colon():
    assert format_time("1830") == "18:30"


def test_format_time_passes_through_short_input():
    assert format_time("18") == "18"


def test_format_date_inserts_dashes():
    assert format_date("20260804") == "2026-08-04"


def test_format_date_passes_through_wrong_length():
    assert format_date("2026-08-04") == "2026-08-04"


def make_showtime(**overrides):
    fields = {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "movie": "테스트 영화",
        "grade": "아이맥스",
        "date": "20260804",
        "time": "1830",
        "screen": "1관",
    }
    fields.update(overrides)
    return CgvShowtime(**fields)


def test_build_signature_joins_fields_in_order():
    entry = make_showtime()
    assert build_signature(entry) == "cgv|20260804|0013|1관|1830|테스트 영화"


def test_save_and_load_showtimes_round_trip(tmp_path):
    showtimes_file = str(tmp_path / "showtimes.json")
    entries = [make_showtime(movie="듄")]

    save_showtimes(showtimes_file, entries, fetched_at="2026-08-14T00:00:00+00:00")

    assert load_showtimes(showtimes_file) == entries


def test_load_showtimes_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    log_error_mock = MagicMock()
    monkeypatch.setattr(monitoring_utils, "log_error", log_error_mock)

    assert load_showtimes(str(tmp_path / "nope.json")) == []
    log_error_mock.assert_not_called()


def test_load_showtimes_returns_empty_list_on_invalid_format(tmp_path):
    showtimes_file = tmp_path / "showtimes.json"
    showtimes_file.write_text("[]", encoding="utf-8")

    assert load_showtimes(str(showtimes_file)) == []


def test_save_and_load_json_list_round_trip(tmp_path):
    file = str(tmp_path / "theaters.json")
    items = [CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰")]

    save_json_list(file, items)

    assert load_json_list(file, CgvTheater) == items


def test_load_json_list_returns_empty_list_when_file_missing(tmp_path):
    assert load_json_list(str(tmp_path / "nope.json"), CgvTheater) == []


def test_load_json_list_returns_empty_list_on_invalid_format(tmp_path):
    file = tmp_path / "theaters.json"
    file.write_text('{"not": "a list"}', encoding="utf-8")

    assert load_json_list(str(file), CgvTheater) == []
