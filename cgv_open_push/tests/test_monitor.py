from monitor import TargetFilter


def make_target(**overrides):
    target = {
        "movie": "",
        "date": "",
        "grades": [],
    }
    target.update(overrides)
    return target


def make_entry(**overrides):
    entry = {
        "prodNm": "듄",
        "tcscnsGradNm": "아이맥스",
    }
    entry.update(overrides)
    return entry


def test_matches_date_true_when_no_date_filter():
    target_filter = TargetFilter(make_target())
    assert target_filter.matches_date("20260810") is True


def test_matches_date_requires_exact_match_when_filter_set():
    target_filter = TargetFilter(make_target(date="20260810"))
    assert target_filter.matches_date("20260810") is True
    assert target_filter.matches_date("20260811") is False


def test_matches_entry_any_grade_when_no_grade_filter():
    target_filter = TargetFilter(make_target(grades=[]))
    assert target_filter.matches_entry(make_entry(tcscnsGradNm="일반")) is True


def test_matches_entry_requires_grade_in_set_when_filter_given():
    target_filter = TargetFilter(make_target(grades=["아이맥스", "4DX"]))
    assert target_filter.matches_entry(make_entry(tcscnsGradNm="아이맥스")) is True
    assert target_filter.matches_entry(make_entry(tcscnsGradNm="일반")) is False


def test_matches_entry_movie_substring_filter():
    target_filter = TargetFilter(make_target(movie="듄"))
    assert target_filter.matches_entry(make_entry(prodNm="듄: 파트2")) is True
    assert target_filter.matches_entry(make_entry(prodNm="탑건")) is False


def test_split_new_entries_baseline_only_returns_no_new_entries():
    target_filter = TargetFilter(make_target())
    entries = [make_entry(), make_entry(scnsrtTm="2000")]

    new_entries, signatures = target_filter.split_new_entries(
        entries, previous_signatures=set(), baseline_only=True
    )

    assert new_entries == []
    assert len(signatures) == 2


def test_split_new_entries_flags_signatures_not_seen_before():
    target_filter = TargetFilter(make_target())
    old_entry = make_entry(scnsrtTm="1800")
    new_entry = make_entry(scnsrtTm="2000")
    from utils import build_signature

    previous_signatures = {build_signature(old_entry)}

    new_entries, signatures = target_filter.split_new_entries(
        [old_entry, new_entry], previous_signatures, baseline_only=False
    )

    assert new_entries == [new_entry]
    assert signatures == {build_signature(old_entry), build_signature(new_entry)}


def test_split_new_entries_excludes_entries_that_do_not_match():
    target_filter = TargetFilter(make_target(movie="듄"))
    non_matching = make_entry(prodNm="탑건")

    new_entries, signatures = target_filter.split_new_entries(
        [non_matching], previous_signatures=set(), baseline_only=False
    )

    assert new_entries == []
    assert signatures == set()
