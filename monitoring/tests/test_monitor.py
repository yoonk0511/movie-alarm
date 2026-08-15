from alarm_bot.targets_store import TargetSpec
from cgv_open_push.cgv_models import CgvShowtime
from monitoring.monitor import Target, TargetRegistry


def make_spec(**overrides):
    fields = {
        "id": "t1",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": [],
        "grades": [],
    }
    fields.update(overrides)
    return TargetSpec(**fields)


def make_target(**overrides):
    fields = {
        "id": "t1",
        "site_name": "용산아이파크몰",
        "movie": "",
        "dates": set(),
        "grades": set(),
    }
    fields.update(overrides)
    return Target(**fields)


def make_entry(**overrides):
    fields = {
        "site_no": "0013",
        "provider": "cgv",
        "site_name": "용산아이파크몰",
        "movie": "듄",
        "grade": "아이맥스",
        "date": "20260810",
        "time": "1800",
        "screen": "1관",
    }
    fields.update(overrides)
    return CgvShowtime(**fields)


def test_matches_true_when_no_filters_set():
    target = make_target()
    assert target.matches(make_entry()) is True


def test_matches_requires_same_site_name():
    target = make_target(site_name="용산아이파크몰")
    assert target.matches(make_entry(site_name="강남")) is False


def test_matches_requires_same_provider():
    target = make_target(provider="cgv")
    assert target.matches(make_entry(provider="megabox")) is False


def test_matches_requires_date_membership_when_filter_set():
    target = make_target(dates={"20260810"})
    assert target.matches(make_entry(date="20260810")) is True
    assert target.matches(make_entry(date="20260811")) is False


def test_matches_requires_grade_in_set_when_filter_given():
    target = make_target(grades={"아이맥스", "4DX"})
    assert target.matches(make_entry(grade="아이맥스")) is True
    assert target.matches(make_entry(grade="일반")) is False


def test_matches_movie_substring_filter():
    target = make_target(movie="듄")
    assert target.matches(make_entry(movie="듄: 파트2")) is True
    assert target.matches(make_entry(movie="탑건")) is False


def test_check_baseline_only_returns_no_new_entries_but_records_signatures():
    target = make_target()
    entries = [make_entry(), make_entry(time="2000")]

    new_entries = target.check(entries, baseline_only=True)

    assert new_entries == []
    assert len(target.previous_signatures) == 2


def test_check_flags_signatures_not_seen_before():
    target = make_target()
    old_entry = make_entry(time="1800")
    target.check([old_entry], baseline_only=True)

    new_entry = make_entry(time="2000")
    new_entries = target.check([old_entry, new_entry], baseline_only=False)

    assert new_entries == [new_entry]
    assert len(target.previous_signatures) == 2


def test_check_excludes_entries_that_do_not_match_other_sites():
    target = make_target(movie="듄", dates={"20260810"})
    entries = [
        make_entry(movie="듄", date="20260810"),
        make_entry(movie="탑건", date="20260810"),
        make_entry(movie="듄", date="20260811"),
    ]

    new_entries = target.check(entries, baseline_only=False)

    assert new_entries == [make_entry(movie="듄", date="20260810")]


def test_from_spec_builds_target_without_touching_any_client():
    spec = make_spec(movie="F1", date=["20260810"], grades=["아이맥스"])

    target = Target.from_spec(spec)

    assert target.id == "t1"
    assert target.site_name == "용산아이파크몰"
    assert target.movie == "F1"
    assert target.dates == {"20260810"}
    assert target.grades == {"아이맥스"}
    assert target.provider == "cgv"


def test_from_spec_reads_explicit_provider():
    spec = make_spec(site_name="메가박스 코엑스", provider="megabox")

    target = Target.from_spec(spec)

    assert target.provider == "megabox"


def test_registry_sync_creates_new_targets_and_flags_them():
    registry = TargetRegistry()
    specs = [make_spec()]

    pairs = registry.sync(specs)

    assert len(pairs) == 1
    target, is_new = pairs[0]
    assert target.id == "t1"
    assert is_new is True


def test_registry_sync_reuses_existing_target_instance_and_marks_not_new():
    registry = TargetRegistry()
    specs = [make_spec()]

    first_target, _ = registry.sync(specs)[0]
    first_target.previous_signatures = {"some-signature"}

    second_target, is_new = registry.sync(specs)[0]

    assert second_target is first_target
    assert is_new is False
    assert second_target.previous_signatures == {"some-signature"}


def test_registry_sync_drops_removed_targets():
    registry = TargetRegistry()
    specs = [make_spec()]
    registry.sync(specs)

    pairs = registry.sync([])

    assert pairs == []
    assert registry.signatures_snapshot() == {}


def test_registry_restore_and_snapshot_signatures_round_trip():
    registry = TargetRegistry()
    specs = [make_spec()]
    registry.sync(specs)

    registry.restore_signatures({"t1": ["sig-a", "sig-b"]})

    assert registry.signatures_snapshot() == {"t1": ["sig-a", "sig-b"]}
