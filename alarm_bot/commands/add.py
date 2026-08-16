import logging
from datetime import datetime

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
    search_dates,
    search_grades,
    search_movies,
    search_theaters,
)

_WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def _with_weekday(date: str) -> str:
    weekday = _WEEKDAY_LABELS[datetime.strptime(date, "%Y%m%d").weekday()]
    return f"{date} ({weekday})"


def _build_confirmation(site: CgvTheater, movie: str, date: str, grades: list[str]) -> str:
    changed, target = add_target(
        site.site_name, grades, movie=movie, date=[date] if date else []
    )
    verb = "추가/변경됨" if changed else "변경 없음 (이미 동일하게 감시 중)"
    return f"**{target.site_name}** ({target.id}) - {describe_target(target)} [{verb}]"


def _build_confirmations(site: CgvTheater, movies: list[str], date: str, grades: list[str]) -> str:
    """영화를 여러 개 고르면 movie마다 별도 target이 생긴다 — TargetSpec.movie가
    문자열 하나짜리 필터라 "영화 A 또는 B" 하나짜리 target은 애초에 표현이
    안 되고, 원래도 영화 하나당 target 하나였다."""
    return "\n".join(_build_confirmation(site, movie, date, grades) for movie in movies)


async def _send_new_targets(interaction, site, movies, date, grades):
    """/add 커맨드 자체에 대한 응답 — followup으로 새 메시지를 보낸다."""
    await interaction.followup.send(_build_confirmations(site, movies, date, grades))


async def _edit_to_targets(interaction, site, movies, date, grades):
    """Select 컴포넌트에 대한 응답 — 고르던 메시지를 결과로 바꿔치기한다."""
    await interaction.response.edit_message(
        content=_build_confirmations(site, movies, date, grades), view=None
    )


def _prompt(site: CgvTheater, text: str) -> str:
    return f"**{site.site_name}** ({site.site_no}) - {text}"


class GradeSelect(discord.ui.Select):
    def __init__(self, site, movies, date, grades):
        self.site = site
        self.movies = movies
        self.date = date
        options = [discord.SelectOption(label=grade, value=grade) for grade in grades[:25]]
        super().__init__(
            placeholder="감시할 등급 선택 (복수 선택 가능, 안 고르면 등급 무관)",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await _edit_to_targets(interaction, self.site, self.movies, self.date, self.values)


class BackToMovieButton(discord.ui.Button):
    """MovieSelect에서 넘어온 GradeSelectView에만 붙는다 — movie를 명령어
    파라미터로 직접 입력한 경우엔 "다시 고를 영화 목록"이 없어서 못 붙인다."""

    def __init__(self, site, date, entries):
        super().__init__(label="◀ 영화 다시 선택", style=discord.ButtonStyle.secondary, row=1)
        self.site = site
        self.date = date
        self.entries = entries

    async def callback(self, interaction: discord.Interaction):
        view = MovieSelectView(site=self.site, date=self.date, entries=self.entries)
        await interaction.response.edit_message(
            content=_prompt(self.site, "감시할 영화를 선택하세요:"), view=view
        )


class GradeSelectView(discord.ui.View):
    def __init__(self, site, movies, date, grades, entries=None):
        super().__init__(timeout=120)
        self.add_item(GradeSelect(site, movies, date, grades))
        if entries is not None:
            self.add_item(BackToMovieButton(site, date, entries))


class MovieSelect(discord.ui.Select):
    def __init__(self, site, date, entries):
        self.site = site
        self.date = date
        self.entries = entries
        movies = distinct_movies(entries)[:24]
        options = [discord.SelectOption(label="전체 영화", value=ALL_MOVIES)]
        options += [discord.SelectOption(label=movie, value=movie) for movie in movies]
        super().__init__(
            placeholder="감시할 영화 선택 (복수 선택 가능)",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # "전체 영화"를 다른 영화와 같이 고르면 의미가 안 맞으니(전체인데 특정
        # 영화만?) 전체가 껴있으면 그걸로 확정 — 나머지 선택은 무시한다.
        movies = [""] if ALL_MOVIES in self.values else list(self.values)
        relevant = (
            self.entries if movies == [""] else [e for e in self.entries if e.movie in movies]
        )
        grades = distinct_grades(relevant)

        if not grades:
            await _edit_to_targets(interaction, self.site, movies, self.date, [])
            return

        view = GradeSelectView(
            site=self.site, movies=movies, date=self.date, grades=grades, entries=self.entries
        )
        await interaction.response.edit_message(
            content=_prompt(self.site, "감시할 등급을 선택하세요:"), view=view
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
    theater = getattr(interaction.namespace, "theater", "")
    matches = search_grades(current, site_name=theater)
    return [app_commands.Choice(name=name, value=name) for name in matches[:25]]


async def date_autocomplete(interaction: discord.Interaction, current: str):
    """theater/movie/grade와 달리 current가 비어 있어도 목록을 보여준다 —
    날짜는 몇 개 안 되니 처음부터 골라 쓰라고 만든 필드라, 뭔가 치라고
    요구하면 오히려 귀찮아진다."""
    theater = getattr(interaction.namespace, "theater", "")
    matches = search_dates(current, site_name=theater)
    return [app_commands.Choice(name=_with_weekday(d), value=d) for d in matches[:25]]


def _normalize_date(date: str) -> str:
    """YYMMDD(6자리)로 입력하면 "20"을 붙여 YYYYMMDD로 확장한다 — 매번 "20"
    치는 게 귀찮아서. 2100년대엔 이 앱이 안 살아있을 테니 century는 하드코딩."""
    if len(date) == 6 and date.isdigit():
        return f"20{date}"
    return date


def _invalid_date_message(date: str) -> str | None:
    if date and not (len(date) == 8 and date.isdigit()):
        return "date는 YYYYMMDD(8자리) 또는 YYMMDD(6자리)로 입력해주세요."
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
    date="감시할 날짜 YYYYMMDD 또는 YYMMDD (자동완성에서 선택 권장, 비우면 가장 가까운 상영일 기준으로 영화/등급 목록을 보여줌)",
)
@app_commands.autocomplete(
    theater=theater_autocomplete,
    movie=movie_autocomplete,
    grade=grade_autocomplete,
    date=date_autocomplete,
)
async def add_cmd(
    interaction: discord.Interaction,
    theater: str,
    movie: str = "",
    grade: str = "",
    date: str = "",
):
    date = _normalize_date(date)
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
        await _send_new_targets(interaction, site, [movie], date, [])
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
            await _send_new_targets(interaction, site, [movie], date, [grade])
            return

        grades = distinct_grades(relevant)
        if not grades:
            await _send_new_targets(interaction, site, [movie], date, [])
            return

        view = GradeSelectView(site=site, movies=[movie], date=date, grades=grades)
        await interaction.followup.send(_prompt(site, "감시할 등급을 선택하세요:"), view=view)
        return

    view = MovieSelectView(site=site, date=date, entries=entries)
    await interaction.followup.send(_prompt(site, "감시할 영화를 선택하세요:"), view=view)
