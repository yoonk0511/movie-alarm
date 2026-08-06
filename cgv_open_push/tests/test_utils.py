import pytest

from utils import build_signature, format_date, format_time, get_base_url, normalize_name


def test_get_base_url_strips_path_and_query():
    assert get_base_url("https://cgv.co.kr/cnm/movieBook/cinema") == "https://cgv.co.kr"


def test_get_base_url_keeps_port():
    assert get_base_url("http://example.com:8080/path?x=1") == "http://example.com:8080"


@pytest.mark.parametrize("bad_url", ["not-a-url", "/relative/path", ""])
def test_get_base_url_rejects_url_without_scheme_or_host(bad_url):
    with pytest.raises(ValueError):
        get_base_url(bad_url)


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


def test_normalize_name_strips_all_whitespace():
    assert normalize_name("씨네드쉐프 용산") == "씨네드쉐프용산"


def test_normalize_name_passes_through_already_normalized():
    assert normalize_name("용산아이파크몰") == "용산아이파크몰"
