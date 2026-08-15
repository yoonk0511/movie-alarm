from unittest.mock import AsyncMock

from cgv_open_push.cgv_models import CgvMovie, CgvShowtime, CgvTheater

from alarm_bot.commands import add as add_cmds

from _bot_test_helpers import make_interaction, make_target, run

SITE = CgvTheater(co_cd="A420", site_no="0013", site_name="용산아이파크몰")


def entry(movie, grade, **overrides):
    fields = {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "movie": movie,
        "grade": grade,
        "date": "20260810",
        "time": "1800",
        "screen": "1관",
    }
    fields.update(overrides)
    return CgvShowtime(**fields)


ENTRIES = [
    entry("듄", "아이맥스"),
    entry("듄", "4DX"),
    entry("탑건", "일반"),
    entry("노그레이드", None),
]


def test_theater_autocomplete_returns_empty_when_query_empty():
    interaction = make_interaction()

    choices = run(add_cmds.theater_autocomplete(interaction, ""))

    assert choices == []


def test_theater_autocomplete_wraps_search_theaters_results(monkeypatch):
    monkeypatch.setattr(
        add_cmds,
        "search_theaters",
        AsyncMock(
            return_value=[
                SITE,
                CgvTheater(co_cd="A420", site_no="P013", site_name="씨네드쉐프 용산"),
            ]
        ),
    )
    interaction = make_interaction()

    choices = run(add_cmds.theater_autocomplete(interaction, "용"))

    assert {c.name for c in choices} == {"용산아이파크몰", "씨네드쉐프 용산"}
    assert {c.value for c in choices} == {"용산아이파크몰", "씨네드쉐프 용산"}


def test_movie_autocomplete_returns_empty_when_query_empty():
    interaction = make_interaction()

    choices = run(add_cmds.movie_autocomplete(interaction, ""))

    assert choices == []


def test_movie_autocomplete_wraps_search_movies_results(monkeypatch):
    monkeypatch.setattr(
        add_cmds,
        "search_movies",
        AsyncMock(
            return_value=[
                CgvMovie(co_cd="A420", movie_no="1", movie_name="오디세이"),
                CgvMovie(co_cd="A420", movie_no="2", movie_name="오디세이(IMAX LASER 2D)"),
            ]
        ),
    )
    interaction = make_interaction()

    choices = run(add_cmds.movie_autocomplete(interaction, "오디"))

    assert {c.name for c in choices} == {"오디세이", "오디세이(IMAX LASER 2D)"}


def test_grade_autocomplete_returns_empty_when_query_empty():
    interaction = make_interaction()

    choices = run(add_cmds.grade_autocomplete(interaction, ""))

    assert choices == []


def test_grade_autocomplete_wraps_search_grades_results(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_grades", lambda query: ["아이맥스"])
    interaction = make_interaction()

    choices = run(add_cmds.grade_autocomplete(interaction, "맥스"))

    assert {c.name for c in choices} == {"아이맥스"}


def test_add_cmd_rejects_invalid_date_format():
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", date="2026-08-10"))

    interaction.response.send_message.assert_called_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    interaction.response.defer.assert_not_called()


def test_add_cmd_adds_directly_when_no_showtimes(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        add_cmds,
        "add_target",
        lambda site_name, grades, movie="", date=None: (
            True,
            make_target(grades=grades, movie=movie, date=date or []),
        ),
    )
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰"))

    interaction.followup.send.assert_called_once()
    message = interaction.followup.send.call_args[0][0]
    assert "등급 무관" in message and "전체 영화" in message


def test_add_cmd_offers_movie_select_when_showtimes_available(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", date="20260810"))

    _, kwargs = interaction.followup.send.call_args
    view = kwargs["view"]
    select = view.children[0]
    assert select.options[0].value == add_cmds.ALL_MOVIES
    assert {o.value for o in select.options[1:]} == {"듄", "탑건", "노그레이드"}
    assert select.date == "20260810"


def test_add_cmd_skips_movie_select_when_movie_given(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(
        add_cmds.add_cmd.callback(
            interaction, theater="용산아이파크몰", movie="듄", date="20260810"
        )
    )

    _, kwargs = interaction.followup.send.call_args
    view = kwargs["view"]
    grade_select = view.children[0]
    assert {o.value for o in grade_select.options} == {"아이맥스", "4DX"}
    assert grade_select.movie == "듄" and grade_select.date == "20260810"


def test_add_cmd_adds_directly_when_movie_given_has_no_grades(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    monkeypatch.setattr(
        add_cmds,
        "add_target",
        lambda site_name, grades, movie="", date=None: (
            True,
            make_target(grades=grades, movie=movie, date=date or []),
        ),
    )
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", movie="노그레이드"))

    interaction.followup.send.assert_called_once()
    message = interaction.followup.send.call_args[0][0]
    assert "노그레이드" in message


def test_add_cmd_resolves_directly_when_movie_and_grade_both_given(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    monkeypatch.setattr(
        add_cmds,
        "add_target",
        lambda site_name, grades, movie="", date=None: (
            True,
            make_target(grades=grades, movie=movie, date=date or []),
        ),
    )
    interaction = make_interaction()

    run(
        add_cmds.add_cmd.callback(
            interaction, theater="용산아이파크몰", movie="듄", grade="4DX"
        )
    )

    interaction.followup.send.assert_called_once()
    message = interaction.followup.send.call_args[0][0]
    assert "듄" in message and "4DX" in message


def test_add_cmd_reports_no_match_when_movie_and_grade_combination_missing(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(
        add_cmds.add_cmd.callback(
            interaction, theater="용산아이파크몰", movie="듄", grade="일반"
        )
    )

    interaction.followup.send.assert_called_once_with(
        "'듄'(일반)에 해당하는 상영 회차를 찾지 못했습니다."
    )


def test_add_cmd_scopes_movie_select_to_grade_when_only_grade_given(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", grade="4DX"))

    _, kwargs = interaction.followup.send.call_args
    select = kwargs["view"].children[0]
    assert {o.value for o in select.options[1:]} == {"듄"}


def test_add_cmd_reports_no_match_when_grade_alone_missing_at_theater(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", AsyncMock(return_value=ENTRIES))
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", grade="SCREENX"))

    interaction.followup.send.assert_called_once_with(
        "'SCREENX' 등급에 해당하는 상영 회차를 찾지 못했습니다."
    )


def test_add_cmd_uses_site_name_not_site_no_for_showtime_lookup(monkeypatch):
    monkeypatch.setattr(add_cmds, "search_theaters", AsyncMock(return_value=[SITE]))
    fetch_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(add_cmds, "fetch_showtimes_for_site", fetch_mock)
    monkeypatch.setattr(add_cmds, "add_target", lambda *a, **k: (True, make_target()))
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산아이파크몰", date="20260810"))

    fetch_mock.assert_awaited_once_with("용산아이파크몰", "20260810")


def test_movie_select_callback_offers_grade_select_for_chosen_movie():
    select = add_cmds.MovieSelect(site=SITE, date="20260810", entries=ENTRIES)
    select._values = ["듄"]
    interaction = make_interaction()

    run(select.callback(interaction))

    _, kwargs = interaction.response.edit_message.call_args
    grade_select = kwargs["view"].children[0]
    assert {o.value for o in grade_select.options} == {"아이맥스", "4DX"}
    assert grade_select.movie == "듄" and grade_select.date == "20260810"


def test_movie_select_callback_adds_directly_when_movie_has_no_grades(monkeypatch):
    captured = {}

    def fake_add_target(site_name, grades, movie="", date=None):
        captured.update(site_name=site_name, grades=grades, movie=movie, date=date)
        return True, make_target(grades=grades, movie=movie, date=date or [])

    monkeypatch.setattr(add_cmds, "add_target", fake_add_target)

    select = add_cmds.MovieSelect(site=SITE, date="", entries=ENTRIES)
    select._values = ["노그레이드"]
    interaction = make_interaction()

    run(select.callback(interaction))

    assert captured == {
        "site_name": "용산아이파크몰",
        "grades": [],
        "movie": "노그레이드",
        "date": [],
    }
    _, kwargs = interaction.response.edit_message.call_args
    assert kwargs["view"] is None


def test_movie_select_callback_all_movies_combines_grades():
    select = add_cmds.MovieSelect(site=SITE, date="", entries=ENTRIES)
    select._values = [add_cmds.ALL_MOVIES]
    interaction = make_interaction()

    run(select.callback(interaction))

    _, kwargs = interaction.response.edit_message.call_args
    grade_select = kwargs["view"].children[0]
    assert {o.value for o in grade_select.options} == {"아이맥스", "4DX", "일반"}
    assert grade_select.movie == ""


def test_grade_select_callback_adds_target_with_chosen_grades(monkeypatch):
    captured = {}

    def fake_add_target(site_name, grades, movie="", date=None):
        captured.update(site_name=site_name, grades=grades, movie=movie, date=date)
        return True, make_target(grades=grades, movie=movie, date=date or [])

    monkeypatch.setattr(add_cmds, "add_target", fake_add_target)

    select = add_cmds.GradeSelect(site=SITE, movie="F1", date="20260810", grades=["아이맥스", "4DX"])
    select._values = ["아이맥스"]
    interaction = make_interaction()

    run(select.callback(interaction))

    assert captured == {
        "site_name": "용산아이파크몰",
        "grades": ["아이맥스"],
        "movie": "F1",
        "date": ["20260810"],
    }
    _, kwargs = interaction.response.edit_message.call_args
    assert "F1" in kwargs["content"] and "20260810" in kwargs["content"]
    assert kwargs["view"] is None


def test_add_cmd_prompts_when_multiple_matches(monkeypatch):
    monkeypatch.setattr(
        add_cmds,
        "search_theaters",
        AsyncMock(
            return_value=[
                SITE,
                CgvTheater(co_cd="A420", site_no="P013", site_name="씨네드쉐프 용산"),
            ]
        ),
    )
    interaction = make_interaction()

    run(add_cmds.add_cmd.callback(interaction, theater="용산"))

    message = interaction.followup.send.call_args[0][0]
    assert "용산아이파크몰" in message
    assert "씨네드쉐프 용산" in message
