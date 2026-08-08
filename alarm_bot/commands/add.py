import logging

import discord
from discord import app_commands

from ..discord_client import GUILD, tree
from ..targets_store import add_target
from ..utils import (
    ALL_MOVIES,
    describe_target,
    distinct_sorted,
    fetch_showtimes_for_site,
    search_theaters,
)


async def _finish_add(interaction, site, movie, date, grades, *, edit: bool):
    changed, target = add_target(
        site["site_name"], grades, movie=movie, date=[date] if date else []
    )
    verb = "추가/변경됨" if changed else "변경 없음 (이미 동일하게 감시 중)"
    content = f"**{target['site_name']}** ({target['id']}) - {describe_target(target)} [{verb}]"
    if edit:
        await interaction.response.edit_message(content=content, view=None)
    else:
        await interaction.followup.send(content)


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
        await _finish_add(interaction, self.site, self.movie, self.date, self.values, edit=True)


class GradeSelectView(discord.ui.View):
    def __init__(self, site, movie, date, grades):
        super().__init__(timeout=120)
        self.add_item(GradeSelect(site, movie, date, grades))


class MovieSelect(discord.ui.Select):
    def __init__(self, site, date, entries):
        self.site = site
        self.date = date
        self.entries = entries
        movies = distinct_sorted(entries, "prodNm")[:24]
        options = [discord.SelectOption(label="전체 영화", value=ALL_MOVIES)]
        options += [discord.SelectOption(label=movie, value=movie) for movie in movies]
        super().__init__(
            placeholder="감시할 영화 선택", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        movie = "" if self.values[0] == ALL_MOVIES else self.values[0]
        relevant = (
            self.entries
            if not movie
            else [e for e in self.entries if str(e.get("prodNm")) == movie]
        )
        grades = distinct_sorted(relevant, "tcscnsGradNm")

        if not grades:
            await _finish_add(interaction, self.site, movie, self.date, [], edit=True)
            return

        view = GradeSelectView(site=self.site, movie=movie, date=self.date, grades=grades)
        await interaction.response.edit_message(
            content=f"**{self.site['site_name']}** ({self.site['site_no']}) - 감시할 등급을 선택하세요:",
            view=view,
        )


class MovieSelectView(discord.ui.View):
    def __init__(self, site, date, entries):
        super().__init__(timeout=120)
        self.add_item(MovieSelect(site, date, entries))


@tree.command(name="add", description="감시 대상 추가", guild=GUILD)
@app_commands.describe(
    theater="추가할 극장 이름 (검색 결과가 하나로 좁혀지는 이름이어야 함)",
    date="감시할 날짜 YYYYMMDD (비우면 가장 가까운 상영일 기준으로 영화/등급 목록을 보여줌)",
)
async def add_cmd(interaction: discord.Interaction, theater: str, date: str = ""):
    if date and not (len(date) == 8 and date.isdigit()):
        await interaction.response.send_message(
            "date는 YYYYMMDD 형식(8자리 숫자)으로 입력해주세요.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    try:
        matches = await search_theaters(theater)
    except Exception as e:
        logging.exception("search_theaters failed")
        await interaction.followup.send(f"극장 검색 실패: {e}")
        return

    exact = [m for m in matches if m["site_name"] == theater]
    if exact:
        matches = exact

    if not matches:
        await interaction.followup.send(f"'{theater}'에 해당하는 극장을 찾지 못했습니다.")
        return
    if len(matches) > 1:
        lines = [f"'{theater}' 검색 결과가 여러 개입니다. 더 정확한 이름으로 다시 시도하세요:"]
        lines += [f"- {m['site_name']} ({m['site_no']})" for m in matches[:15]]
        await interaction.followup.send("\n".join(lines))
        return

    site = matches[0]
    try:
        entries = await fetch_showtimes_for_site(site["site_name"], date or None)
    except Exception as e:
        logging.exception("fetch_showtimes_for_site failed")
        await interaction.followup.send(f"상영 스케줄 조회 실패: {e}")
        return

    if not entries:
        await _finish_add(interaction, site, "", date, [], edit=False)
        return

    view = MovieSelectView(site=site, date=date, entries=entries)
    await interaction.followup.send(
        f"**{site['site_name']}** ({site['site_no']}) - 감시할 영화를 선택하세요:", view=view
    )
