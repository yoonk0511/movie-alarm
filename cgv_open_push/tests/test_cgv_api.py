import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cgv_api import CgvApiClient, CgvApiError, CgvTheaterClient
from cgv_models import CgvMovie, CgvTheater


def run(coro):
    return asyncio.run(coro)


def make_response(
    payload=None, *, ok=True, status=200, url="https://cgv.co.kr/api", json_error=False
):
    response = MagicMock()
    response.ok = ok
    response.status = status
    response.url = url
    if json_error:
        response.json = AsyncMock(side_effect=ValueError("bad json"))
    else:
        response.json = AsyncMock(return_value=payload)
    return response


def make_request(*responses):
    request = MagicMock()
    request.get = AsyncMock(side_effect=list(responses))
    return request


def test_get_json_returns_parsed_dict_on_success():
    request = make_request(make_response({"data": []}))
    client = CgvApiClient(request, co_cd="A420")

    result = run(client._get_json("/some/path", {"a": "b"}))

    assert result == {"data": []}
    request.get.assert_awaited_once_with(
        "/some/path",
        params={"a": "b"},
        headers={"Accept": "application/json"},
        timeout=30_000,
    )


def test_get_json_raises_on_non_ok_response():
    request = make_request(make_response(ok=False, status=500, url="https://x"))
    client = CgvApiClient(request, co_cd="A420")

    with pytest.raises(CgvApiError, match="status=500"):
        run(client._get_json("/some/path", {}))


def test_get_json_raises_on_invalid_json():
    request = make_request(make_response(json_error=True))
    client = CgvApiClient(request, co_cd="A420")

    with pytest.raises(CgvApiError, match="invalid JSON"):
        run(client._get_json("/some/path", {}))


def test_get_json_raises_on_non_dict_response():
    request = make_request(make_response(["not", "a", "dict"]))
    client = CgvApiClient(request, co_cd="A420")

    with pytest.raises(CgvApiError, match="unexpected CGV API response type"):
        run(client._get_json("/some/path", {}))


def test_fetch_regn_list_calls_expected_endpoint():
    request = make_request(make_response({"data": []}))
    client = CgvApiClient(request, co_cd="A420")

    run(client.fetch_regn_list())

    args, kwargs = request.get.call_args
    assert args[0] == "/api/v1/booking/searchRegnList"
    assert kwargs["params"] == {"coCd": "A420"}


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
    request = make_request(make_response(payload))
    client = CgvApiClient(request, co_cd="A420")

    theaters = run(client.fetch_regn_list())

    assert [(t.site_no, t.site_name) for t in theaters] == [
        ("0013", "용산아이파크몰"),
        ("0056", "강남"),
    ]
    assert all(isinstance(t, CgvTheater) for t in theaters)


def test_fetch_movie_list_calls_expected_endpoint():
    request = make_request(make_response({"data": []}))
    client = CgvApiClient(request, co_cd="A420")

    run(client.fetch_movie_list())

    args, kwargs = request.get.call_args
    assert args[0] == "/api/v1/booking/searchAtktTopPostrList"
    assert kwargs["params"] == {"coCd": "A420", "movNm": "", "div": "", "attrCd": ""}


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
    request = make_request(make_response(payload))
    client = CgvApiClient(request, co_cd="A420")

    movies = run(client.fetch_movie_list())

    assert len(movies) == 1
    movie = movies[0]
    assert isinstance(movie, CgvMovie)
    assert movie.movie_no == "30001323"
    assert movie.movie_name == "오디세이"
    assert movie.booking_rate == "51.46"


def make_theater_client(request, *, site_no="0013", co_cd="A420", site_name="용산아이파크몰"):
    """site_no가 이미 알려진 상태로 시작하는 테스트용 헬퍼 — _resolve_site_no의
    이름 검색 로직 자체는 아래 test_resolve_site_no_* 에서 따로 검증한다."""
    client = CgvTheaterClient(request, site_name=site_name, co_cd=co_cd)
    client._site_no = site_no
    return client


def make_regn_list_payload(*theaters):
    return {"data": [{"siteList": [dict(t) for t in theaters]}]}


def test_resolve_site_no_finds_exact_name_match():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"},
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    request = make_request(make_response(payload))
    client = CgvTheaterClient(request, site_name="용산아이파크몰", co_cd="A420")

    site_no = run(client._resolve_site_no())

    assert site_no == "0013"


def test_resolve_site_no_ignores_whitespace_differences():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    request = make_request(make_response(payload))
    client = CgvTheaterClient(request, site_name="씨네드쉐프용산", co_cd="A420")

    site_no = run(client._resolve_site_no())

    assert site_no == "P013"


def test_resolve_site_no_caches_result_across_calls():
    payload = make_regn_list_payload({"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"})
    request = make_request(make_response(payload))
    client = CgvTheaterClient(request, site_name="용산아이파크몰", co_cd="A420")

    run(client._resolve_site_no())
    run(client._resolve_site_no())

    request.get.assert_awaited_once()


def test_resolve_site_no_raises_when_no_match():
    payload = make_regn_list_payload({"coCd": "A420", "siteNo": "0056", "siteNm": "강남"})
    request = make_request(make_response(payload))
    client = CgvTheaterClient(request, site_name="없는극장", co_cd="A420")

    with pytest.raises(CgvApiError, match="no theater matches"):
        run(client._resolve_site_no())


def test_resolve_site_no_raises_when_ambiguous():
    payload = make_regn_list_payload(
        {"coCd": "A420", "siteNo": "0013", "siteNm": "용산아이파크몰"},
        {"coCd": "A420", "siteNo": "P013", "siteNm": "씨네드쉐프 용산"},
    )
    request = make_request(make_response(payload))
    client = CgvTheaterClient(request, site_name="용산", co_cd="A420")

    with pytest.raises(CgvApiError, match="ambiguous theater name"):
        run(client._resolve_site_no())


def test_fetch_scheduled_dates_extracts_scn_ymd_values():
    request = make_request(
        make_response({"data": [{"scnYmd": "20260810"}, {"scnYmd": "20260811"}]})
    )
    client = make_theater_client(request)

    dates = run(client.fetch_scheduled_dates())

    assert dates == ["20260810", "20260811"]


def test_fetch_scheduled_dates_skips_malformed_rows():
    request = make_request(
        make_response({"data": [{"scnYmd": "20260810"}, {"noYmd": True}, "not-a-dict", None]})
    )
    client = make_theater_client(request)

    dates = run(client.fetch_scheduled_dates())

    assert dates == ["20260810"]


def test_fetch_scheduled_dates_raises_when_data_not_list():
    request = make_request(make_response({"data": {"not": "a list"}}))
    client = make_theater_client(request)

    with pytest.raises(CgvApiError, match="not a list"):
        run(client.fetch_scheduled_dates())


def test_fetch_showtimes_filters_non_dict_entries_and_sends_expected_params():
    request = make_request(make_response({"data": [{"prodNm": "듄"}, "garbage"]}))
    client = make_theater_client(request)

    entries = run(client.fetch_showtimes("20260810"))

    assert entries == [{"prodNm": "듄"}]
    args, kwargs = request.get.call_args
    assert kwargs["params"] == {
        "coCd": "A420",
        "siteNo": "0013",
        "scnYmd": "20260810",
        "rtctlScopCd": "08",
    }


def test_fetch_showtimes_raises_when_data_not_list():
    request = make_request(make_response({"data": "not-a-list"}))
    client = make_theater_client(request)

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
