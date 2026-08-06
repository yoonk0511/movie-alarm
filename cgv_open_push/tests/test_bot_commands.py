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


def make_target(**overrides):
    target = {
        "id": "0013",
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": "",
        "grades": ["아이맥스", "4DX"],
    }
    target.update(overrides)
    return target


def test_targets_cmd_reports_when_no_targets(monkeypatch):
    monkeypatch.setattr(bot, "load_targets", lambda: [])
    interaction = make_interaction()

    run(bot.targets_cmd.callback(interaction))

    interaction.response.send_message.assert_called_once_with("감시 중인 대상이 없습니다.")


def test_targets_cmd_lists_each_target(monkeypatch):
    monkeypatch.setattr(bot, "load_targets", lambda: [make_target()])
    interaction = make_interaction()

    run(bot.targets_cmd.callback(interaction))

    message = interaction.response.send_message.call_args[0][0]
    assert "[0013] 용산아이파크몰 (0013)" in message
    assert "전체 영화 / 전체 날짜 / 아이맥스, 4DX" in message


def test_targets_cmd_shows_movie_and_date_filters(monkeypatch):
    monkeypatch.setattr(
        bot, "load_targets", lambda: [make_target(movie="F1", date="20260810", grades=[])]
    )
    interaction = make_interaction()

    run(bot.targets_cmd.callback(interaction))

    message = interaction.response.send_message.call_args[0][0]
    assert "F1 / 20260810 / 등급 무관" in message


def test_search_cmd_reports_no_match(monkeypatch):
    monkeypatch.setattr(bot, "search_theaters", AsyncMock(return_value=[]))
    interaction = make_interaction()

    run(bot.search_cmd.callback(interaction, "없는극장"))

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_called_once_with(
        "'없는극장'에 해당하는 극장을 찾지 못했습니다."
    )


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


def test_add_cmd_rejects_invalid_date_format():
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산아이파크몰", date="2026-08-10"))

    interaction.response.send_message.assert_called_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    interaction.response.defer.assert_not_called()


ENTRIES = [
    {"prodNm": "듄", "tcscnsGradNm": "아이맥스"},
    {"prodNm": "듄", "tcscnsGradNm": "4DX"},
    {"prodNm": "탑건", "tcscnsGradNm": "일반"},
    {"prodNm": "노그레이드"},
]


def test_add_cmd_adds_directly_when_no_showtimes(monkeypatch):
    monkeypatch.setattr(
        bot,
        "search_theaters",
        AsyncMock(return_value=[{"site_no": "0013", "site_name": "용산아이파크몰"}]),
    )
    monkeypatch.setattr(bot, "fetch_showtimes_for_site", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        bot,
        "add_target",
        lambda site_no, site_name, grades, movie="", date="": (
            True,
            make_target(grades=grades, movie=movie, date=date),
        ),
    )
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산아이파크몰"))

    interaction.followup.send.assert_called_once()
    message = interaction.followup.send.call_args[0][0]
    assert "등급 무관" in message and "전체 영화" in message


def test_add_cmd_offers_movie_select_when_showtimes_available(monkeypatch):
    monkeypatch.setattr(
        bot,
        "search_theaters",
        AsyncMock(return_value=[{"site_no": "0013", "site_name": "용산아이파크몰"}]),
    )
    monkeypatch.setattr(bot, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(bot.add_cmd.callback(interaction, theater="용산아이파크몰", date="20260810"))

    _, kwargs = interaction.followup.send.call_args
    view = kwargs["view"]
    select = view.children[0]
    assert select.options[0].value == bot.ALL_MOVIES
    assert {o.value for o in select.options[1:]} == {"듄", "탑건", "노그레이드"}
    assert select.date == "20260810"


def test_movie_select_callback_offers_grade_select_for_chosen_movie():
    site = {"site_no": "0013", "site_name": "용산아이파크몰"}
    select = bot.MovieSelect(site=site, date="20260810", entries=ENTRIES)
    select._values = ["듄"]
    interaction = make_interaction()

    run(select.callback(interaction))

    _, kwargs = interaction.response.edit_message.call_args
    grade_select = kwargs["view"].children[0]
    assert {o.value for o in grade_select.options} == {"아이맥스", "4DX"}
    assert grade_select.movie == "듄" and grade_select.date == "20260810"


def test_movie_select_callback_adds_directly_when_movie_has_no_grades(monkeypatch):
    captured = {}

    def fake_add_target(site_no, site_name, grades, movie="", date=""):
        captured.update(site_no=site_no, site_name=site_name, grades=grades, movie=movie, date=date)
        return True, make_target(grades=grades, movie=movie, date=date)

    monkeypatch.setattr(bot, "add_target", fake_add_target)

    site = {"site_no": "0013", "site_name": "용산아이파크몰"}
    select = bot.MovieSelect(site=site, date="", entries=ENTRIES)
    select._values = ["노그레이드"]
    interaction = make_interaction()

    run(select.callback(interaction))

    assert captured["grades"] == [] and captured["movie"] == "노그레이드"
    _, kwargs = interaction.response.edit_message.call_args
    assert kwargs["view"] is None


def test_movie_select_callback_all_movies_combines_grades():
    site = {"site_no": "0013", "site_name": "용산아이파크몰"}
    select = bot.MovieSelect(site=site, date="", entries=ENTRIES)
    select._values = [bot.ALL_MOVIES]
    interaction = make_interaction()

    run(select.callback(interaction))

    _, kwargs = interaction.response.edit_message.call_args
    grade_select = kwargs["view"].children[0]
    assert {o.value for o in grade_select.options} == {"아이맥스", "4DX", "일반"}
    assert grade_select.movie == ""


def test_grade_select_callback_adds_target_with_chosen_grades(monkeypatch):
    captured = {}

    def fake_add_target(site_no, site_name, grades, movie="", date=""):
        captured.update(site_no=site_no, site_name=site_name, grades=grades, movie=movie, date=date)
        return True, make_target(grades=grades, movie=movie, date=date)

    monkeypatch.setattr(bot, "add_target", fake_add_target)

    site = {"site_no": "0013", "site_name": "용산아이파크몰"}
    select = bot.GradeSelect(site=site, movie="F1", date="20260810", grades=["아이맥스", "4DX"])
    select._values = ["아이맥스"]
    interaction = make_interaction()

    run(select.callback(interaction))

    assert captured == {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "grades": ["아이맥스"],
        "movie": "F1",
        "date": "20260810",
    }
    _, kwargs = interaction.response.edit_message.call_args
    assert "F1" in kwargs["content"] and "20260810" in kwargs["content"]
    assert kwargs["view"] is None


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

    run(bot.add_cmd.callback(interaction, theater="용산"))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰" in message
    assert "씨네드쉐프 용산" in message


def test_remove_cmd_removes_matching_target_by_id(monkeypatch):
    monkeypatch.setattr(bot, "load_targets", lambda: [make_target()])
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


def test_remove_cmd_prompts_when_multiple_matches_by_name(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [
            make_target(id="a1", movie="F1"),
            make_target(id="a2", movie="탑건"),
        ],
    )
    interaction = make_interaction()

    run(bot.remove_cmd.callback(interaction, "용산아이파크몰"))

    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    message = interaction.response.send_message.call_args[0][0]
    assert "a1" in message and "a2" in message


def test_remove_autocomplete_filters_by_site_name(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [
            make_target(id="a1"),
            make_target(id="a2", site_name="강변", site_no="0001"),
        ],
    )
    interaction = make_interaction()

    choices = run(bot.remove_autocomplete(interaction, "용산"))

    assert len(choices) == 1
    assert choices[0].value == "a1"


def test_remove_autocomplete_filters_by_movie(monkeypatch):
    monkeypatch.setattr(
        bot,
        "load_targets",
        lambda: [
            make_target(id="a1", movie="F1"),
            make_target(id="a2", movie="탑건"),
        ],
    )
    interaction = make_interaction()

    choices = run(bot.remove_autocomplete(interaction, "F1"))

    assert len(choices) == 1
    assert choices[0].value == "a1"
