from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from cgv_open_push.cgv_models import CgvMovie, CgvShowtime, CgvTheater

from alarm_bot import utils

from _bot_test_helpers import make_target, run


@asynccontextmanager
async def fake_browser_session(page=None):
    yield page or MagicMock()


# --- search_theaters / fetch_showtimes_for_site (CgvApiClient/CgvTheaterClient wiring) ---


def test_search_theaters_filters_cached_list_by_query_substring(monkeypatch):
    cached = [
        CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰"),
        CgvTheater(co_cd="A420", site_no="0056", site_name="강남"),
    ]
    monkeypatch.setattr(utils, "load_json_list", lambda file, cls: cached)

    matches = run(utils.search_theaters("용산"))

    assert matches == [CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰")]


def test_search_theaters_returns_empty_when_no_match(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_json_list",
        lambda file, cls: [CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰")],
    )

    assert run(utils.search_theaters("없는극장")) == []


def test_search_theaters_falls_back_to_live_fetch_when_cache_empty(monkeypatch):
    theaters = [
        CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰"),
        CgvTheater(co_cd="A420", site_no="0056", site_name="강남"),
    ]
    fake_client = MagicMock()
    fake_client.fetch_regn_list = AsyncMock(return_value=theaters)
    monkeypatch.setattr(utils, "load_json_list", lambda file, cls: [])
    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvApiClient", lambda page: fake_client)

    matches = run(utils.search_theaters("용산"))

    assert matches == [CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰")]


def test_search_movies_filters_cached_list_by_query_substring(monkeypatch):
    cached = [
        CgvMovie(co_cd="A420", movie_no="1", movie_name="오디세이"),
        CgvMovie(co_cd="A420", movie_no="2", movie_name="탑건"),
    ]
    monkeypatch.setattr(utils, "load_json_list", lambda file, cls: cached)

    matches = run(utils.search_movies("오디"))

    assert [m.movie_name for m in matches] == ["오디세이"]


def test_search_movies_falls_back_to_live_fetch_when_cache_empty(monkeypatch):
    movies = [
        CgvMovie(co_cd="A420", movie_no="1", movie_name="오디세이"),
        CgvMovie(co_cd="A420", movie_no="2", movie_name="탑건"),
    ]
    fake_client = MagicMock()
    fake_client.fetch_movie_list = AsyncMock(return_value=movies)
    monkeypatch.setattr(utils, "load_json_list", lambda file, cls: [])
    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvApiClient", lambda page: fake_client)

    matches = run(utils.search_movies("오디"))

    assert [m.movie_name for m in matches] == ["오디세이"]


def make_showtime(**overrides):
    fields = {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "movie": "듄",
        "grade": "아이맥스",
        "date": "20260810",
        "time": "1800",
        "screen": "1관",
    }
    fields.update(overrides)
    return CgvShowtime(**fields)


def test_search_grades_filters_observed_grades_by_substring(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_showtimes",
        lambda file: [make_showtime(grade="아이맥스"), make_showtime(grade="4DX")],
    )

    assert utils.search_grades("맥스") == ["아이맥스"]


def test_search_grades_returns_empty_for_unobserved_grade(monkeypatch):
    monkeypatch.setattr(utils, "load_showtimes", lambda file: [make_showtime(grade="아이맥스")])

    assert utils.search_grades("Laser") == []


def test_search_grades_scopes_to_site_name_when_given(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_showtimes",
        lambda file: [
            make_showtime(site_name="용산아이파크몰", grade="아이맥스"),
            make_showtime(site_name="강남", grade="4DX"),
        ],
    )

    assert utils.search_grades("", site_name="용산아이파크몰") == ["아이맥스"]


def test_search_grades_falls_back_to_all_sites_when_scoped_site_has_no_showtimes(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_showtimes",
        lambda file: [make_showtime(site_name="강남", grade="4DX")],
    )

    assert utils.search_grades("", site_name="없는극장") == ["4DX"]


def test_search_dates_dedupes_and_sorts_observed_dates(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_showtimes",
        lambda file: [
            make_showtime(date="20260811"),
            make_showtime(date="20260810"),
            make_showtime(date="20260810"),
        ],
    )

    assert utils.search_dates("") == ["20260810", "20260811"]


def test_search_dates_scopes_to_site_name_when_given(monkeypatch):
    monkeypatch.setattr(
        utils,
        "load_showtimes",
        lambda file: [
            make_showtime(site_name="용산아이파크몰", date="20260810"),
            make_showtime(site_name="강남", date="20260811"),
        ],
    )

    assert utils.search_dates("", site_name="용산아이파크몰") == ["20260810"]


def test_fetch_showtimes_for_site_uses_site_name_not_site_no(monkeypatch):
    captured = {}
    showtime = CgvShowtime(
        site_no="0013",
        site_name="용산아이파크몰",
        movie="듄",
        grade="아이맥스",
        date="20260810",
        time="1830",
        screen="1관",
    )

    class FakeTheaterClient:
        def __init__(self, page, site_name):
            captured["site_name"] = site_name

        async def fetch_showtime_entries(self, scn_ymd=None):
            captured["scn_ymd"] = scn_ymd
            return [showtime]

    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvTheaterClient", FakeTheaterClient)

    entries = run(utils.fetch_showtimes_for_site("용산아이파크몰", "20260810"))

    assert entries == [showtime]
    assert captured == {"site_name": "용산아이파크몰", "scn_ymd": "20260810"}


# --- pure helpers ---


def test_distinct_movies_dedupes_and_sorts():
    entries = [
        CgvShowtime("0013", "용산", "듄", "아이맥스", "20260810", "1800", "1관"),
        CgvShowtime("0013", "용산", "탑건", "아이맥스", "20260810", "2000", "1관"),
        CgvShowtime("0013", "용산", "듄", "4DX", "20260810", "2100", "2관"),
    ]
    assert utils.distinct_movies(entries) == ["듄", "탑건"]


def test_distinct_grades_dedupes_and_sorts():
    entries = [
        CgvShowtime("0013", "용산", "듄", "아이맥스", "20260810", "1800", "1관"),
        CgvShowtime("0013", "용산", "듄", "4DX", "20260810", "2000", "2관"),
        CgvShowtime("0013", "용산", "탑건", "4DX", "20260810", "2100", "2관"),
    ]
    assert utils.distinct_grades(entries) == ["4DX", "아이맥스"]


def test_distinct_grades_skips_entries_with_no_grade():
    entries = [CgvShowtime("0013", "용산", "노그레이드", None, "20260810", "1800", "1관")]
    assert utils.distinct_grades(entries) == []


def test_describe_target_joins_multiple_dates_and_grades():
    target = make_target(movie="F1", date=["20260810", "20260811"], grades=["4DX", "아이맥스"])
    assert utils.describe_target(target) == "F1 / 20260810, 20260811 / 4DX, 아이맥스"


def test_describe_target_defaults_when_empty():
    target = make_target(movie="", date=[], grades=[])
    assert utils.describe_target(target) == "전체 영화 / 전체 날짜 / 등급 무관"
