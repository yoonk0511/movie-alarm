from unittest.mock import MagicMock

from alarm_bot.targets_store import TargetSpec
from cgv_open_push.cgv_models import CgvShowtime
from monitoring.match import build_notification_message, check_all_targets
from monitoring.monitor import TargetRegistry


def make_entry(**overrides):
    fields = {
        "site_no": "0013",
        "provider": "cgv",
        "site_name": "용산아이파크몰",
        "movie": "오디세이",
        "grade": "아이맥스",
        "date": "20260815",
        "time": "0730",
        "screen": "IMAX관",
    }
    fields.update(overrides)
    return CgvShowtime(**fields)


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


def test_build_notification_message_formats_date_time_and_footer():
    message = build_notification_message("용산아이파크몰", [make_entry()])

    assert "용산아이파크몰 예매 오픈 알림" in message
    assert "2026-08-15" in message
    assert "07:30" in message
    assert "[아이맥스] 오디세이 (IMAX관)" in message


def test_check_all_targets_sends_discord_only_for_matching_new_entries(monkeypatch):
    registry = TargetRegistry()
    targets = [make_spec(movie="오디세이", grades=["아이맥스"])]
    entries = [make_entry(), make_entry(movie="탑건")]

    send_mock = MagicMock()
    monkeypatch.setattr("monitoring.match.send_discord", send_mock)

    # target의 첫 sync는 항상 baseline_only라 여기선 알림이 안 나간다 —
    # 두 번째 라운드에서 처음 본 signature여야 "새 회차"로 잡힌다.
    check_all_targets(registry, targets, [], first_run=False)
    check_all_targets(registry, targets, entries, first_run=False)

    send_mock.assert_called_once()
    _, kwargs = send_mock.call_args
    assert "오디세이" in kwargs["content"]
    assert "탑건" not in kwargs["content"]


def test_check_all_targets_sends_nothing_on_baseline_run(monkeypatch):
    registry = TargetRegistry()
    targets = [make_spec()]
    entries = [make_entry()]

    send_mock = MagicMock()
    monkeypatch.setattr("monitoring.match.send_discord", send_mock)

    check_all_targets(registry, targets, entries, first_run=True)

    send_mock.assert_not_called()


def test_check_all_targets_skips_target_whose_check_raises(monkeypatch):
    registry = TargetRegistry()
    targets = [
        make_spec(),
        make_spec(id="t2", site_name="강남"),
    ]

    send_mock = MagicMock()
    monkeypatch.setattr("monitoring.match.send_discord", send_mock)

    # 두 target 다 baseline부터 잡아둔다 (빈 스냅샷).
    check_all_targets(registry, targets, [], first_run=False)

    t1 = registry.sync(targets)[0][0]
    t1.check = MagicMock(side_effect=RuntimeError("boom"))

    entries = [make_entry(site_name="강남")]
    check_all_targets(registry, targets, entries, first_run=False)

    send_mock.assert_called_once()
    _, kwargs = send_mock.call_args
    assert "강남" in kwargs["content"]
