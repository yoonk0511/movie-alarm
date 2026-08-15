import logging

import discord
from discord import app_commands

from cgv_open_push.cgv_models import CgvTheater

from ..discord_client import GUILD, tree
from ..targets_store import add_target
from ..utils import (
    ALL_MOVIES,
    describe_target,
    distinct_grades,
    distinct_movies,
    fetch_showtimes_for_site,
    search_grades,
    search_movies,
    search_theaters,
)


def _build_confirmation(site: CgvTheater, movie: str, date: str, grades: list[str]) -> str:
    changed, target = add_target(
        site.site_name, grades, movie=movie, date=[date] if date else []
    )
    verb = "추가/변경됨" if changed else "변경 없음 (이미 동일하게 감시 중)"
    return f"**{target.site_name}** ({target.id}) - {describe_target(target)} [{verb}]"


async def _send_new_target(interaction, site, movie, date, grades):
    """/add 커맨드 자체에 대한 응답 — followup으로 새 메시지를 보낸다."""
    await interaction.followup.send(_build_confirmation(site, movie, date, grades))


async def _edit_to_target(interaction, site, movie, date, grades):
    """Select 컴포넌트에 대한 응답 — 고르던 메시지를 결과로 바꿔치기한다."""
    await interaction.response.edit_message(
        content=_build_confirmation(site, movie, date, grades), view=None
    )


class GradeSelect(discord.ui.Select):
    def __init__(self, site, movie, date, grades):
        options = [discord.SelectOption(label=grade, value=grade) for grade in grades]
        super().__init__(
            placeholder="감시할 등급 선택 (복수 선택 가능, 안 고르면 등급 무관)",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self.site = site
        self.movie = movie
        self.date = date

    async def callback(self, interaction: discord.Interaction):
        await _edit_to_target(interaction, self.site, self.movie, self.date, self.values)


class GradeSelectView(discord.ui.View):
    def __init__(self, site, movie, date, grades):
        super().__init__(timeout=120)
        self.add_item(GradeSelect(site, movie, date, grades))


class MovieSelect(discord.ui.Select):
    def __init__(self, site, date, entries):
        self.site = site
        self.date = date
        self.entries = entries
        movies = distinct_movies(entries)[:24]
        options = [discord.SelectOption(label="전체 영화", value=ALL_MOVIES)]
        options += [discord.SelectOption(label=movie, value=movie) for movie in movies]
        super().__init__(
            placeholder="감시할 영화 선택", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        movie = "" if self.values[0] == ALL_MOVIES else self.values[0]
        relevant = self.entries if not movie else [e for e in self.entries if e.movie == movie]
        grades = distinct_grades(relevant)

        if not grades:
            await _edit_to_target(interaction, self.site, movie, self.date, [])
            return

        view = GradeSelectView(site=self.site, movie=movie, date=self.date, grades=grades)
        await interaction.response.edit_message(
            content=f"**{self.site.site_name}** ({self.site.site_no}) - 감시할 등급을 선택하세요:",
            view=view,
        )


class MovieSelectView(discord.ui.View):
    def __init__(self, site, date, entries):
        super().__init__(timeout=120)
        self.add_item(MovieSelect(site, date, entries))


async def theater_autocomplete(interaction: discord.Interaction, current: str):
    if not current:
        return []
    matches = await search_theaters(current)
    return [app_commands.Choice(name=m.site_name, value=m.site_name) for m in matches[:25]]


async def movie_autocomplete(interaction: discord.Interaction, current: str):
    if not current:
        return []
    matches = await search_movies(current)
    return [app_commands.Choice(name=m.movie_name, value=m.movie_name) for m in matches[:25]]


async def grade_autocomplete(interaction: discord.Interaction, current: str):
    if not current:
        return []
    matches = search_grades(current)
    return [app_commands.Choice(name=name, value=name) for name in matches[:25]]


def _invalid_date_message(date: str) -> str | None:
    if date and not (len(date) == 8 and date.isdigit()):
        return "date는 YYYYMMDD 형식(8자리 숫자)으로 입력해주세요."
    return None


async def _resolve_single_theater(theater_query: str) -> tuple[CgvTheater | None, str | None]:
    """(theater, error_message)를 돌려준다 — 하나로 안 좁혀지면 theater=None에
    error_message로 이유(못 찾음/여러 개 걸림)를 담는다."""
    matches = await search_theaters(theater_query)
    exact = [m for m in matches if m.site_name == theater_query]
    if exact:
        matches = exact

    if not matches:
        return None, f"'{theater_query}'에 해당하는 극장을 찾지 못했습니다."
    if len(matches) > 1:
        lines = [f"'{theater_query}' 검색 결과가 여러 개입니다. 더 정확한 이름으로 다시 시도하세요:"]
        lines += [f"- {m.site_name} ({m.site_no})" for m in matches[:15]]
        return None, "\n".join(lines)

    return matches[0], None


@tree.command(name="add", description="감시 대상 추가", guild=GUILD)
@app_commands.describe(
    theater="추가할 극장 이름 (자동완성에서 선택 권장)",
    movie="감시할 영화 (비우면 상영 회차 목록에서 고름, 자동완성에서 선택 권장)",
    grade="감시할 등급/포맷 - 아이맥스, 4DX 등 (비우면 등급 선택 목록을 보여줌)",
    date="감시할 날짜 YYYYMMDD (비우면 가장 가까운 상영일 기준으로 영화/등급 목록을 보여줌)",
)
@app_commands.autocomplete(
    theater=theater_autocomplete, movie=movie_autocomplete, grade=grade_autocomplete
)
async def add_cmd(
    interaction: discord.Interaction,
    theater: str,
    movie: str = "",
    grade: str = "",
    date: str = "",
):
    invalid_date = _invalid_date_message(date)
    if invalid_date:
        await interaction.response.send_message(invalid_date, ephemeral=True)
        return

    await interaction.response.defer()

    try:
        site, error = await _resolve_single_theater(theater)
    except Exception as e:
        logging.exception("search_theaters failed")
        await interaction.followup.send(f"극장 검색 실패: {e}")
        return
    if error:
        await interaction.followup.send(error)
        return

    try:
        entries = await fetch_showtimes_for_site(site.site_name, date or None)
    except Exception as e:
        logging.exception("fetch_showtimes_for_site failed")
        await interaction.followup.send(f"상영 스케줄 조회 실패: {e}")
        return

    if grade:
        entries = [e for e in entries if e.grade == grade]
        if not entries:
            await interaction.followup.send(f"'{grade}' 등급에 해당하는 상영 회차를 찾지 못했습니다.")
            return

    if not entries:
        await _send_new_target(interaction, site, movie, date, [])
        return

    if movie:
        relevant = [e for e in entries if movie in e.movie]

        if grade:
            # movie와 grade가 둘 다 정해졌으니 더 고를 게 없다 — 바로 끝낸다.
            if not relevant:
                await interaction.followup.send(
                    f"'{movie}'({grade})에 해당하는 상영 회차를 찾지 못했습니다."
                )
                return
            await _send_new_target(interaction, site, movie, date, [grade])
            return

        grades = distinct_grades(relevant)
        if not grades:
            await _send_new_target(interaction, site, movie, date, [])
            return

        view = GradeSelectView(site=site, movie=movie, date=date, grades=grades)
        await interaction.followup.send(
            f"**{site.site_name}** ({site.site_no}) - 감시할 등급을 선택하세요:", view=view
        )
        return

    view = MovieSelectView(site=site, date=date, entries=entries)
    await interaction.followup.send(
        f"**{site.site_name}** ({site.site_no}) - 감시할 영화를 선택하세요:", view=view
    )
