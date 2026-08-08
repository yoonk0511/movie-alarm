from unittest.mock import AsyncMock

from alarm_bot.commands import search as search_cmds

from _bot_test_helpers import make_interaction, run


def test_search_cmd_reports_no_match(monkeypatch):
    monkeypatch.setattr(search_cmds, "search_theaters", AsyncMock(return_value=[]))
    interaction = make_interaction()

    run(search_cmds.search_cmd.callback(interaction, "없는극장"))

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_called_once_with(
        "'없는극장'에 해당하는 극장을 찾지 못했습니다."
    )


def test_search_cmd_lists_matches(monkeypatch):
    monkeypatch.setattr(
        search_cmds,
        "search_theaters",
        AsyncMock(return_value=[{"site_no": "0013", "site_name": "용산아이파크몰"}]),
    )
    interaction = make_interaction()

    run(search_cmds.search_cmd.callback(interaction, "용산"))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰 (0013)" in message


def test_search_cmd_reports_failure(monkeypatch):
    monkeypatch.setattr(
        search_cmds, "search_theaters", AsyncMock(side_effect=RuntimeError("boom"))
    )
    interaction = make_interaction()

    run(search_cmds.search_cmd.callback(interaction, "용산"))

    interaction.followup.send.assert_called_once_with("검색 실패: boom")
