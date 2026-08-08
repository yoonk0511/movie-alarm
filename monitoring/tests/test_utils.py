from monitoring.utils import build_signature, format_date, format_time


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
        "scnYmd": "20260804",
        "siteNo": "0013",
        "scnsNm": "1관",
        "scnsrtTm": "1830",
        "prodNm": "테스트 영화",
    }
    assert build_signature(entry) == "20260804|0013|1관|1830|테스트 영화"


def test_build_signature_defaults_missing_fields_to_empty_string():
    assert build_signature({}) == "||||"
