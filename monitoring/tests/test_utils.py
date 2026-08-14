from monitoring.utils import (
    build_signature,
    format_date,
    format_time,
    load_showtimes,
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


def test_build_signature_joins_fields_in_order():
    entry = {
        "provider": "cgv",
        "date": "20260804",
        "site_no": "0013",
        "screen": "1관",
        "time": "1830",
        "movie": "테스트 영화",
    }
    assert build_signature(entry) == "cgv|20260804|0013|1관|1830|테스트 영화"


def test_build_signature_defaults_missing_fields_to_empty_string():
    assert build_signature({}) == "|||||"


def test_save_and_load_showtimes_round_trip(tmp_path):
    showtimes_file = str(tmp_path / "showtimes.json")
    entries = [{"provider": "cgv", "site_name": "용산아이파크몰", "movie": "듄"}]

    save_showtimes(showtimes_file, entries, fetched_at="2026-08-14T00:00:00+00:00")

    assert load_showtimes(showtimes_file) == entries


def test_load_showtimes_returns_empty_list_when_file_missing(tmp_path):
    assert load_showtimes(str(tmp_path / "nope.json")) == []


def test_load_showtimes_returns_empty_list_on_invalid_format(tmp_path):
    showtimes_file = tmp_path / "showtimes.json"
    showtimes_file.write_text("[]", encoding="utf-8")

    assert load_showtimes(str(showtimes_file)) == []
