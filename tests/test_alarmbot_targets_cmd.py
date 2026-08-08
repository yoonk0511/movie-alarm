from alarm_bot.commands import targets as targets_cmds

from _bot_test_helpers import make_interaction, make_target, run


def test_targets_cmd_reports_when_no_targets(monkeypatch):
    monkeypatch.setattr(targets_cmds, "load_targets", lambda: [])
    interaction = make_interaction()

    run(targets_cmds.targets_cmd.callback(interaction))

    interaction.response.send_message.assert_called_once_with("감시 중인 대상이 없습니다.")


def test_targets_cmd_lists_each_target(monkeypatch):
    monkeypatch.setattr(targets_cmds, "load_targets", lambda: [make_target()])
    interaction = make_interaction()

    run(targets_cmds.targets_cmd.callback(interaction))

    message = interaction.response.send_message.call_args[0][0]
    assert "[0013] 용산아이파크몰 -" in message
    assert "전체 영화 / 전체 날짜 / 아이맥스, 4DX" in message
