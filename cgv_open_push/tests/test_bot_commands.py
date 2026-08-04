import asyncio
from unittest.mock import AsyncMock, MagicMock

import bot


def make_interaction():
    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def run(coro):
    return asyncio.run(coro)


def test_targets_cmd_reports_when_no_targets(monkeypatch):
    monkeypatch.setattr(bot, "load_targets", lambda: [])
    interaction = make_interaction()

    run(bot.targets_cmd.callback(interaction))

    interaction.response.send_message.assert_called_once_with("감시 중인 대상이 없습니다.")


def test_targets_cmd_lists_each_target(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [{"site_no": "0013", "site_name": "용산아이파크몰", "grades": ["아이맥스", "4DX"]}],
    )
    interaction = make_interaction()

    run(bot.targets_cmd.callback(interaction))

    message = interaction.response.send_message.call_args[0][0]
    assert "용산아이파크몰 (0013): 아이맥스, 4DX" in message


def test_search_cmd_reports_no_match(monkeypatch):
    monkeypatch.setattr(bot, "search_theaters", AsyncMock(return_value=[]))
    interaction = make_interaction()

    run(bot.search_cmd.callback(interaction, "없는극장"))

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_called_once_with("'없는극장'에 해당하는 극장을 찾지 못했습니다.")


def test_search_cmd_lists_matches(monkeypatch):
    monkeypatch.setattr(
        bot,
        "search_theaters",
        AsyncMock(return_value=[{"site_no": "0013", "site_name": "용산아이파크몰"}]),
    )
    interaction = make_interaction()

    run(bot.search_cmd.callback(interaction, "용산"))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰 (0013)" in message


def test_search_cmd_reports_failure(monkeypatch):
    monkeypatch.setattr(bot, "search_theaters", AsyncMock(side_effect=RuntimeError("boom")))
    interaction = make_interaction()

    run(bot.search_cmd.callback(interaction, "용산"))

    interaction.followup.send.assert_called_once_with("검색 실패: boom")


def test_add_cmd_rejects_when_no_grade_selected():
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산아이파크몰"))

    interaction.response.send_message.assert_called_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    interaction.response.defer.assert_not_called()


def test_add_cmd_adds_target_on_single_match(monkeypatch):
    monkeypatch.setattr(
        bot,
        "search_theaters",
        AsyncMock(return_value=[{"site_no": "0013", "site_name": "용산아이파크몰"}]),
    )
    monkeypatch.setattr(
        bot,
        "add_target",
        lambda site_no, site_name, grades: (
            True,
            {"site_no": site_no, "site_name": site_name, "grades": grades},
        ),
    )
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산아이파크몰", imax=True))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰" in message
    assert "추가/변경됨" in message


def test_add_cmd_prompts_when_multiple_matches(monkeypatch):
    monkeypatch.setattr(
        bot,
        "search_theaters",
        AsyncMock(
            return_value=[
                {"site_no": "0013", "site_name": "용산아이파크몰"},
                {"site_no": "P013", "site_name": "씨네드쉐프 용산"},
            ]
        ),
    )
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산", imax=True))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰" in message
    assert "씨네드쉐프 용산" in message


def test_remove_cmd_removes_matching_target(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [{"site_no": "0013", "site_name": "용산아이파크몰", "grades": ["아이맥스"]}],
    )
    remove_mock = MagicMock()
    monkeypatch.setattr(bot, "remove_target", remove_mock)
    interaction = make_interaction()

    run(bot.remove_cmd.callback(interaction, "0013"))

    remove_mock.assert_called_once_with("0013")
    message = interaction.response.send_message.call_args[0][0]
    assert "용산아이파크몰" in message


def test_remove_cmd_reports_when_not_found(monkeypatch):
    monkeypatch.setattr(bot, "load_targets", lambda: [])
    interaction = make_interaction()

    run(bot.remove_cmd.callback(interaction, "없는극장"))

    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


def test_remove_autocomplete_filters_by_substring(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [
            {"site_no": "0013", "site_name": "용산아이파크몰", "grades": ["아이맥스"]},
            {"site_no": "0001", "site_name": "강변", "grades": ["일반"]},
        ],
    )
    interaction = make_interaction()

    choices = run(bot.remove_autocomplete(interaction, "용산"))

    assert len(choices) == 1
    assert choices[0].value == "0013"
