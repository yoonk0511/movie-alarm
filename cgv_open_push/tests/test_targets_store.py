import targets_store


def _isolate(tmp_path, monkeypatch, default_targets=None):
    targets_file = tmp_path / "targets.json"
    monkeypatch.setattr(targets_store, "TARGETS_FILE", str(targets_file))
    monkeypatch.setattr(targets_store, "DEFAULT_TARGETS", default_targets or [])
    return targets_file


def test_add_new_target_creates_entry(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    changed, target = targets_store.add_target("0013", "용산아이파크몰", ["아이맥스", "4DX"])

    assert changed is True
    assert target == {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "grades": ["4DX", "아이맥스"],
    }
    assert targets_store.load_targets() == [target]


def test_add_target_merges_grades_for_existing_site(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    targets_store.add_target("0013", "용산아이파크몰", ["아이맥스"])
    changed, target = targets_store.add_target("0013", "용산아이파크몰", ["4DX"])

    assert changed is True
    assert target["grades"] == ["4DX", "아이맥스"]


def test_add_target_reports_no_change_when_grades_already_present(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    targets_store.add_target("0013", "용산아이파크몰", ["아이맥스", "4DX"])
    changed, target = targets_store.add_target("0013", "용산아이파크몰", ["아이맥스"])

    assert changed is False
    assert target["grades"] == ["4DX", "아이맥스"]


def test_remove_target_deletes_matching_entry(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    targets_store.add_target("0013", "용산아이파크몰", ["아이맥스"])

    assert targets_store.remove_target("0013") is True
    assert targets_store.load_targets() == []


def test_remove_target_returns_false_when_not_found(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    assert targets_store.remove_target("9999") is False


def test_load_targets_creates_file_from_defaults_when_missing(tmp_path, monkeypatch):
    default_targets = [{"site_no": "0013", "site_name": "용산아이파크몰", "grades": ["아이맥스"]}]
    targets_file = _isolate(tmp_path, monkeypatch, default_targets=default_targets)

    result = targets_store.load_targets()

    assert result == default_targets
    assert targets_file.exists()
