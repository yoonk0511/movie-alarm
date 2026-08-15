from cgv_open_push.cgv_models import CgvShowtime


def test_cgv_showtime_from_api_maps_fields_and_defaults_provider_to_cgv():
    raw = {
        "siteNo": "0013",
        "prodNm": "오디세이",
        "tcscnsGradNm": "아이맥스",
        "scnYmd": "20260815",
        "scnsrtTm": "0730",
        "scnsNm": "IMAX관",
    }

    showtime = CgvShowtime.from_api(raw, site_name="용산아이파크몰")

    assert showtime.site_no == "0013"
    assert showtime.site_name == "용산아이파크몰"
    assert showtime.movie == "오디세이"
    assert showtime.grade == "아이맥스"
    assert showtime.date == "20260815"
    assert showtime.time == "0730"
    assert showtime.screen == "IMAX관"
    assert showtime.provider == "cgv"


def test_cgv_showtime_from_api_defaults_missing_fields():
    showtime = CgvShowtime.from_api({}, site_name="용산아이파크몰")

    assert showtime.site_no == ""
    assert showtime.movie == ""
    assert showtime.grade is None
    assert showtime.date == ""
    assert showtime.time == ""
    assert showtime.screen is None
