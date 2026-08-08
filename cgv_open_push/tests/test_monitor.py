import asyncio
from unittest.mock import AsyncMock, MagicMock

from cgv_open_push.cgv_api import CgvTheaterClient
from cgv_open_push.monitor import Target, TargetRegistry


def run(coro):
    return asyncio.run(coro)


def make_theater(scheduled_dates, showtimes_by_date):
    theater = MagicMock()
    theater.fetch_scheduled_dates = AsyncMock(return_value=scheduled_dates)
    theater.fetch_showtimes = AsyncMock(
        side_effect=lambda scn_ymd: showtimes_by_date.get(scn_ymd, [])
    )
    return theater


def make_target(theater=None, **overrides):
    fields = {
        "id": "t1",
        "site_name": "용산아이파크몰",
        "movie": "",
        "dates": set(),
        "grades": set(),
        "theater": theater or make_theater([], {}),
    }
    fields.update(overrides)
    return Target(**fields)


def make_entry(**overrides):
    entry = {
        "prodNm": "듄",
        "tcscnsGradNm": "아이맥스",
    }
    entry.update(overrides)
    return entry


def test_matches_date_true_when_no_date_filter():
    target = make_target(dates=set())
    assert target.matches_date("20260810") is True


def test_matches_date_requires_membership_when_filter_set():
    target = make_target(dates={"20260810"})
    assert target.matches_date("20260810") is True
    assert target.matches_date("20260811") is False


def test_matches_date_allows_any_date_in_set():
    target = make_target(dates={"20260810", "20260815"})
    assert target.matches_date("20260810") is True
    assert target.matches_date("20260815") is True
    assert target.matches_date("20260811") is False


def test_matches_entry_any_grade_when_no_grade_filter():
    target = make_target(grades=set())
    assert target.matches_entry(make_entry(tcscnsGradNm="일반")) is True


def test_matches_entry_requires_grade_in_set_when_filter_given():
    target = make_target(grades={"아이맥스", "4DX"})
    assert target.matches_entry(make_entry(tcscnsGradNm="아이맥스")) is True
    assert target.matches_entry(make_entry(tcscnsGradNm="일반")) is False


def test_matches_entry_movie_substring_filter():
    target = make_target(movie="듄")
    assert target.matches_entry(make_entry(prodNm="듄: 파트2")) is True
    assert target.matches_entry(make_entry(prodNm="탑건")) is False


def test_check_baseline_only_returns_no_new_entries_but_records_signatures():
    theater = make_theater(["20260810"], {"20260810": [make_entry(), make_entry(scnsrtTm="2000")]})
    target = make_target(theater=theater)

    new_entries = run(target.check(baseline_only=True))

    assert new_entries == []
    assert len(target.previous_signatures) == 2


def test_check_flags_signatures_not_seen_before():
    old_entry = make_entry(scnsrtTm="1800")
    new_entry = make_entry(scnsrtTm="2000")
    theater = make_theater(["20260810"], {"20260810": [old_entry]})
    target = make_target(theater=theater)
    run(target.check(baseline_only=True))

    theater.fetch_showtimes = AsyncMock(return_value=[old_entry, new_entry])
    new_entries = run(target.check(baseline_only=False))

    assert new_entries == [new_entry]
    assert len(target.previous_signatures) == 2


def test_check_excludes_entries_that_do_not_match_and_skips_dates():
    theater = make_theater(
        ["20260810", "20260811"],
        {
            "20260810": [make_entry(prodNm="듄"), make_entry(prodNm="탑건")],
            "20260811": [make_entry(prodNm="듄")],
        },
    )
    target = make_target(theater=theater, movie="듄", dates={"20260810"})

    new_entries = run(target.check(baseline_only=False))

    assert new_entries == [make_entry(prodNm="듄")]
    theater.fetch_showtimes.assert_awaited_once_with("20260810")


def test_from_dict_builds_theater_client_from_site_name():
    page = MagicMock()
    data = {
        "id": "t1",
        "site_name": "용산아이파크몰",
        "movie": "F1",
        "date": ["20260810"],
        "grades": ["아이맥스"],
    }

    target = Target.from_dict(data, page)

    assert target.id == "t1"
    assert target.site_name == "용산아이파크몰"
    assert target.movie == "F1"
    assert target.dates == {"20260810"}
    assert target.grades == {"아이맥스"}
    assert isinstance(target.theater, CgvTheaterClient)
    assert target.theater.site_name == "용산아이파크몰"


def test_registry_sync_creates_new_targets_and_flags_them():
    registry = TargetRegistry(MagicMock())
    data = [{"id": "t1", "site_name": "용산아이파크몰", "movie": "", "date": [], "grades": []}]

    pairs = registry.sync(data)

    assert len(pairs) == 1
    target, is_new = pairs[0]
    assert target.id == "t1"
    assert is_new is True


def test_registry_sync_reuses_existing_target_instance_and_marks_not_new():
    registry = TargetRegistry(MagicMock())
    data = [{"id": "t1", "site_name": "용산아이파크몰", "movie": "", "date": [], "grades": []}]

    first_target, _ = registry.sync(data)[0]
    first_target.previous_signatures = {"some-signature"}

    second_target, is_new = registry.sync(data)[0]

    assert second_target is first_target
    assert is_new is False
    assert second_target.previous_signatures == {"some-signature"}


def test_registry_sync_drops_removed_targets():
    registry = TargetRegistry(MagicMock())
    data = [{"id": "t1", "site_name": "용산아이파크몰", "movie": "", "date": [], "grades": []}]
    registry.sync(data)

    pairs = registry.sync([])

    assert pairs == []
    assert registry.signatures_snapshot() == {}


def test_registry_restore_and_snapshot_signatures_round_trip():
    registry = TargetRegistry(MagicMock())
    data = [{"id": "t1", "site_name": "용산아이파크몰", "movie": "", "date": [], "grades": []}]
    registry.sync(data)

    registry.restore_signatures({"t1": ["sig-a", "sig-b"]})

    assert registry.signatures_snapshot() == {"t1": ["sig-a", "sig-b"]}
