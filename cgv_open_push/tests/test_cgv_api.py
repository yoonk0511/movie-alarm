import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from cgv_open_push.cgv_api import CgvApiClient, CgvApiError, CgvTheaterClient
from cgv_open_push.cgv_models import CgvMovie, CgvTheater


def run(coro):
    return asyncio.run(coro)


def make_evaluate_result(
    payload=None, *, ok=True, status=200, url="https://cgv.co.kr/api", json_error=False
):
    body = "not-json" if json_error else json.dumps(payload)
    return {"ok": ok, "status": status, "url": url, "body": body}


def make_page(*results):
    page = MagicMock()
    page.evaluate = AsyncMock(side_effect=list(results))
    return page


def called_url(page):
    args, _kwargs = page.evaluate.call_args
    return args[1]


def test_get_json_returns_parsed_dict_on_success():
    page = make_page(make_evaluate_result({"data": []}))
    client = CgvApiClient(page, co_cd="A420")

    result = run(client._get_json("/some/path", {"a": "b"}))

    assert result == {"data": []}
    assert called_url(page) == "/some/path?a=b"


def test_get_json_raises_on_non_ok_response():
    page = make_page(make_evaluate_result(ok=False, status=500, url="https://x"))
    client = CgvApiClient(page, co_cd="A420")

    with pytest.raises(CgvApiError, match="status=500"):
        run(client._get_json("/some/path", {}))


def test_get_json_raises_on_invalid_json():
    page = make_page(make_evaluate_result(json_error=True))
    client = CgvApiClient(page, co_cd="A420")

    with pytest.raises(CgvApiError, match="invalid JSON"):
        run(client._get_json("/some/path", {}))


def test_get_json_raises_on_non_dict_response():
    page = make_page(make_evaluate_result(["not", "a", "dict"]))
    client = CgvApiClient(page, co_cd="A420")

    with pytest.raises(CgvApiError, match="unexpected CGV API response type"):
        run(client._get_json("/some/path", {}))


def test_fetch_regn_list_calls_expected_endpoint():
    page = make_page(make_evaluate_result({"data": []}))
    client = CgvApiClient(page, co_cd="A420")

    run(client.fetch_regn_list())

    assert called_url(page) == "/api/v1/booking/searchRegnList?coCd=A420"


def test_fetch_regn_list_flattens_regions_into_theaters():
    payload = {
        "data": [
            {
                "siteList": [
                    {"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"},
                    "garbage",
                ]
            },
            "garbage-region",
            {"siteList": [{"coCd": "A420", "siteNo": "0056", "siteNm": "강남"}]},
        ]
    }
    page = make_page(make_evaluate_result(payload))
    client = CgvApiClient(page, co_cd="A420")

    theaters = run(client.fetch_regn_list())

    assert [(t.site_no, t.site_name) for t in theaters] == [
        ("0013", "용산아이파크몰"),
        ("0056", "강남"),
    ]
    assert all(isinstance(t, CgvTheater) for t in theaters)


def test_fetch_movie_list_calls_expected_endpoint():
    page = make_page(make_evaluate_result({"data": []}))
    client = CgvApiClient(page, co_cd="A420")

    run(client.fetch_movie_list())

    assert (
        called_url(page) == "/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd="
    )


def test_fetch_movie_list_parses_entries_into_movies():
    payload = {
        "data": [
            {
                "coCd": "A420",
                "movNo": "30001323",
                "movNm": "오디세이",
                "i320Fnm": "30001323_320.jpg",
                "scnBssTm": "172",
                "cratgClsCd": "02",
                "atktRate": "51.46",
                "mblUrl": None,
            },
            "garbage",
        ]
    }
    page = make_page(make_evaluate_result(payload))
    client = CgvApiClient(page, co_cd="A420")

    movies = run(client.fetch_movie_list())

    assert len(movies) == 1
    movie = movies[0]
    assert isinstance(movie, CgvMovie)
    assert movie.movie_no == "30001323"
    assert movie.movie_name == "오디세이"
    assert movie.booking_rate == "51.46"


def make_theater_client(page, *, site_no="0013", co_cd="A420", site_name="용산아이파크몰"):
    """site_no가 이미 알려진 상태로 시작하는 테스트용 헬퍼 — _resolve_site_no의
    이름 검색 로직 자체는 아래 test_resolve_site_no_* 에서 따로 검증한다."""
    client = CgvTheaterClient(page, site_name=site_name, co_cd=co_cd)
    client._site_no = site_no
    return client


def make_regn_list_payload(*theaters):
    return {"data": [{"siteList": [dict(t) for t in theaters]}]}


def test_resolve_site_no_finds_exact_name_match():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"},
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    page = make_page(make_evaluate_result(payload))
    client = CgvTheaterClient(page, site_name="용산아이파크몰", co_cd="A420")

    site_no = run(client._resolve_site_no())

    assert site_no == "0013"


def test_resolve_site_no_ignores_whitespace_differences():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    page = make_page(make_evaluate_result(payload))
    client = CgvTheaterClient(page, site_name="씨네드쉐프용산", co_cd="A420")

    site_no = run(client._resolve_site_no())

    assert site_no == "P013"


def test_resolve_site_no_caches_result_across_calls():
    payload = make_regn_list_payload({"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"})
    page = make_page(make_evaluate_result(payload))
    client = CgvTheaterClient(page, site_name="용산아이파크몰", co_cd="A420")

    run(client._resolve_site_no())
    run(client._resolve_site_no())

    page.evaluate.assert_awaited_once()


def test_resolve_site_no_raises_when_no_match():
    payload = make_regn_list_payload({"coCd": "A420", "siteNo": "0056", "siteNm": "강남"})
    page = make_page(make_evaluate_result(payload))
    client = CgvTheaterClient(page, site_name="없는극장", co_cd="A420")

    with pytest.raises(CgvApiError, match="no theater matches"):
        run(client._resolve_site_no())


def test_resolve_site_no_raises_when_ambiguous():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"},
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    page = make_page(make_evaluate_result(payload))
    client = CgvTheaterClient(page, site_name="용산", co_cd="A420")

    with pytest.raises(CgvApiError, match="ambiguous theater name"):
        run(client._resolve_site_no())


def test_fetch_scheduled_dates_extracts_scn_ymd_values():
    page = make_page(
        make_evaluate_result({"data": [{"scnYmd": "20260810"}, {"scnYmd": "20260811"}]})
    )
    client = make_theater_client(page)

    dates = run(client.fetch_scheduled_dates())

    assert dates == ["20260810", "20260811"]


def test_fetch_scheduled_dates_skips_malformed_rows():
    page = make_page(
        make_evaluate_result(
            {"data": [{"scnYmd": "20260810"}, {"noYmd": True}, "not-a-dict", None]}
        )
    )
    client = make_theater_client(page)

    dates = run(client.fetch_scheduled_dates())

    assert dates == ["20260810"]


def test_fetch_scheduled_dates_raises_when_data_not_list():
    page = make_page(make_evaluate_result({"data": {"not": "a list"}}))
    client = make_theater_client(page)

    with pytest.raises(CgvApiError, match="not a list"):
        run(client.fetch_scheduled_dates())


def test_fetch_showtimes_filters_non_dict_entries_and_sends_expected_params():
    page = make_page(make_evaluate_result({"data": [{"prodNm": "듄"}, "garbage"]}))
    client = make_theater_client(page)

    entries = run(client.fetch_showtimes("20260810"))

    assert entries == [{"prodNm": "듄"}]
    assert called_url(page) == (
        "/api/v1/booking/searchMovScnInfo?coCd=A420&siteNo=0013&scnYmd=20260810&rtctlScopCd=08"
    )


def test_fetch_showtimes_raises_when_data_not_list():
    page = make_page(make_evaluate_result({"data": "not-a-list"}))
    client = make_theater_client(page)

    with pytest.raises(CgvApiError, match="not a list"):
        run(client.fetch_showtimes("20260810"))


def test_fetch_showtime_entries_uses_given_date_without_looking_up_schedule(monkeypatch):
    client = make_theater_client(MagicMock())
    monkeypatch.setattr(client, "fetch_scheduled_dates", AsyncMock())
    monkeypatch.setattr(client, "fetch_showtimes", AsyncMock(return_value=[{"prodNm": "듄"}]))

    entries = run(client.fetch_showtime_entries("20260810"))

    assert entries == [{"prodNm": "듄"}]
    client.fetch_scheduled_dates.assert_not_called()
    client.fetch_showtimes.assert_awaited_once_with("20260810")


def test_fetch_showtime_entries_falls_back_to_nearest_scheduled_date(monkeypatch):
    client = make_theater_client(MagicMock())
    monkeypatch.setattr(
        client, "fetch_scheduled_dates", AsyncMock(return_value=["20260810", "20260811"])
    )
    monkeypatch.setattr(client, "fetch_showtimes", AsyncMock(return_value=[{"prodNm": "듄"}]))

    entries = run(client.fetch_showtime_entries())

    assert entries == [{"prodNm": "듄"}]
    client.fetch_showtimes.assert_awaited_once_with("20260810")


def test_fetch_showtime_entries_returns_empty_when_no_scheduled_dates(monkeypatch):
    client = make_theater_client(MagicMock())
    monkeypatch.setattr(client, "fetch_scheduled_dates", AsyncMock(return_value=[]))
    fetch_showtimes = AsyncMock()
    monkeypatch.setattr(client, "fetch_showtimes", fetch_showtimes)

    entries = run(client.fetch_showtime_entries())

    assert entries == []
    fetch_showtimes.assert_not_called()
