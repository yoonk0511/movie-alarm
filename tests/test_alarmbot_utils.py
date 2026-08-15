import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from cgv_open_push.cgv_models import CgvMovie, CgvTheater

from alarm_bot import utils


def run(coro):
    return asyncio.run(coro)


def make_target(**overrides):
    target = {
        "id": "0013",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": [],
        "grades": ["아이맥스", "4DX"],
    }
    target.update(overrides)
    return target


@asynccontextmanager
async def fake_browser_session(page=None):
    yield page or MagicMock()


# --- search_theaters / fetch_showtimes_for_site (CgvApiClient/CgvTheaterClient wiring) ---


def test_search_theaters_filters_cached_list_by_query_substring(monkeypatch):
    cached = [
        {"site_no": "0013", "site_name": "용산아이파크몰"},
        {"site_no": "0056", "site_name": "강남"},
    ]
    monkeypatch.setattr(utils, "load_json_list", lambda file: cached)

    matches = run(utils.search_theaters("용산"))

    assert matches == [{"site_no": "0013", "site_name": "용산아이파크몰"}]


def test_search_theaters_returns_empty_when_no_match(monkeypatch):
    monkeypatch.setattr(
        utils, "load_json_list", lambda file: [{"site_no": "0013", "site_name": "용산아이파크몰"}]
    )

    assert run(utils.search_theaters("없는극장")) == []


def test_search_theaters_falls_back_to_live_fetch_when_cache_empty(monkeypatch):
    theaters = [
        CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰"),
        CgvTheater(co_cd="A420", site_no="0056", site_name="강남"),
    ]
    fake_client = MagicMock()
    fake_client.fetch_regn_list = AsyncMock(return_value=theaters)
    monkeypatch.setattr(utils, "load_json_list", lambda file: [])
    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvApiClient", lambda page: fake_client)

    matches = run(utils.search_theaters("용산"))

    assert matches == [{"site_no": "0013", "site_name": "용산아이파크몰"}]


def test_search_movies_filters_cached_list_by_query_substring(monkeypatch):
    cached = [{"movie_name": "오디세이"}, {"movie_name": "탑건"}]
    monkeypatch.setattr(utils, "load_json_list", lambda file: cached)

    assert run(utils.search_movies("오디")) == ["오디세이"]


def test_search_movies_falls_back_to_live_fetch_when_cache_empty(monkeypatch):
    movies = [
        CgvMovie(co_cd="A420", movie_no="1", movie_name="오디세이"),
        CgvMovie(co_cd="A420", movie_no="2", movie_name="탑건"),
    ]
    fake_client = MagicMock()
    fake_client.fetch_movie_list = AsyncMock(return_value=movies)
    monkeypatch.setattr(utils, "load_json_list", lambda file: [])
    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvApiClient", lambda page: fake_client)

    assert run(utils.search_movies("오디")) == ["오디세이"]


def test_fetch_showtimes_for_site_uses_site_name_not_site_no(monkeypatch):
    captured = {}

    class FakeTheaterClient:
        def __init__(self, page, site_name):
            captured["site_name"] = site_name

        async def fetch_showtime_entries(self, scn_ymd=None):
            captured["scn_ymd"] = scn_ymd
            return [{"prodNm": "듄"}]

    monkeypatch.setattr(utils, "cgv_browser_session", fake_browser_session)
    monkeypatch.setattr(utils, "CgvTheaterClient", FakeTheaterClient)

    entries = run(utils.fetch_showtimes_for_site("용산아이파크몰", "20260810"))

    assert entries == [{"prodNm": "듄"}]
    assert captured == {"site_name": "용산아이파크몰", "scn_ymd": "20260810"}


# --- pure helpers ---


def test_distinct_sorted_dedupes_and_sorts():
    entries = [{"g": "4DX"}, {"g": "아이맥스"}, {"g": "4DX"}, {}]
    assert utils.distinct_sorted(entries, "g") == ["4DX", "아이맥스"]


def test_describe_target_joins_multiple_dates_and_grades():
    target = make_target(movie="F1", date=["20260810", "20260811"], grades=["4DX", "아이맥스"])
    assert utils.describe_target(target) == "F1 / 20260810, 20260811 / 4DX, 아이맥스"


def test_describe_target_defaults_when_empty():
    target = make_target(movie="", date=[], grades=[])
    assert utils.describe_target(target) == "전체 영화 / 전체 날짜 / 등급 무관"
