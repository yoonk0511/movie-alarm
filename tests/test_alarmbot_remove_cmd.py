from unittest.mock import MagicMock

from alarm_bot.commands import remove as remove_cmds

from _bot_test_helpers import make_interaction, make_target, run


def test_remove_cmd_removes_matching_target_by_id(monkeypatch):
    monkeypatch.setattr(remove_cmds, "load_targets", lambda: [make_target()])
    remove_mock = MagicMock()
    monkeypatch.setattr(remove_cmds, "remove_target", remove_mock)
    interaction = make_interaction()

    run(remove_cmds.remove_cmd.callback(interaction, "0013"))

    remove_mock.assert_called_once_with("0013")
    message = interaction.response.send_message.call_args[0][0]
    assert "용산아이파크몰" in message


def test_remove_cmd_reports_when_not_found(monkeypatch):
    monkeypatch.setattr(remove_cmds, "load_targets", lambda: [])
    interaction = make_interaction()

    run(remove_cmds.remove_cmd.callback(interaction, "없는극장"))

    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


def test_remove_cmd_prompts_when_multiple_matches_by_name(monkeypatch):
    monkeypatch.setattr(
        remove_cmds,
        "load_targets",
        lambda: [
            make_target(id="a1", movie="F1"),
            make_target(id="a2", movie="탑건"),
        ],
    )
    interaction = make_interaction()

    run(remove_cmds.remove_cmd.callback(interaction, "용산아이파크몰"))

    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    message = interaction.response.send_message.call_args[0][0]
    assert "a1" in message and "a2" in message


def test_remove_autocomplete_filters_by_site_name(monkeypatch):
    monkeypatch.setattr(
        remove_cmds,
        "load_targets",
        lambda: [
            make_target(id="a1"),
            make_target(id="a2", site_name="강변"),
        ],
    )
    interaction = make_interaction()

    choices = run(remove_cmds.remove_autocomplete(interaction, "용산"))

    assert len(choices) == 1
    assert choices[0].value == "a1"


def test_remove_autocomplete_filters_by_movie(monkeypatch):
    monkeypatch.setattr(
        remove_cmds,
        "load_targets",
        lambda: [
            make_target(id="a1", movie="F1"),
            make_target(id="a2", movie="탑건"),
        ],
    )
    interaction = make_interaction()

    choices = run(remove_cmds.remove_autocomplete(interaction, "F1"))

    assert len(choices) == 1
    assert choices[0].value == "a1"
