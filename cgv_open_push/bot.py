import logging
from contextlib import asynccontextmanager
from datetime import datetime

import discord
from discord import app_commands
from playwright.async_api import async_playwright

from cgv_api import fetch_regn_list, fetch_showtime_entries
from config import (
    BOOKING_PAGE_URL,
    CO_CD,
    DISCORD_BOT_TOKEN,
    DISCORD_GUILD_ID,
    LOG_FILE,
    USER_AGENT,
)
from targets_store import add_target, load_targets, remove_target
from utils import get_base_url

logging.basicConfig(
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)

GUILD = discord.Object(id=int(DISCORD_GUILD_ID)) if DISCORD_GUILD_ID else None

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@asynccontextmanager
async def cgv_browser_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            base_url=get_base_url(BOOKING_PAGE_URL),
        )
        page = await context.new_page()
        await page.goto(BOOKING_PAGE_URL, timeout=30000, wait_until="networkidle")
        try:
            yield context.request
        finally:
            await browser.close()


async def search_theaters(query):
    async with cgv_browser_session() as request:
        result = await fetch_regn_list(request, CO_CD)

    matches = []
    for region in result.get("data") or []:
        for site in region.get("siteList") or []:
            if query in site["siteNm"]:
                matches.append({"site_no": site["siteNo"], "site_name": site["siteNm"]})
    return matches


async def fetch_showtimes_for_site(site_no, scn_ymd=None):
    async with cgv_browser_session() as request:
        return await fetch_showtime_entries(request, CO_CD, site_no, scn_ymd)


def _distinct_sorted(entries, field):
    return sorted({str(entry[field]) for entry in entries if entry.get(field)})


def describe_target(t):
    movie_desc = t.get("movie") or "전체 영화"
    date_desc = t.get("date") or "전체 날짜"
    grade_desc = ", ".join(t["grades"]) if t["grades"] else "등급 무관"
    return f"{movie_desc} / {date_desc} / {grade_desc}"


@tree.command(
    name="targets", description="현재 감시 중인 극장/영화/날짜/등급 목록 조회", guild=GUILD
)
async def targets_cmd(interaction: discord.Interaction):
    targets = load_targets()
    if not targets:
        await interaction.response.send_message("감시 중인 대상이 없습니다.")
        return
    lines = ["**현재 감시 대상**"]
    for t in targets:
        lines.append(f"- [{t['id']}] {t['site_name']} ({t['site_no']}) - {describe_target(t)}")
    await interaction.response.send_message("\n".join(lines))


@tree.command(name="search", description="극장 이름으로 site_no 검색", guild=GUILD)
@app_commands.describe(query="검색할 극장 이름 (일부만 입력해도 됨)")
async def search_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        matches = await search_theaters(query)
    except Exception as e:
        logging.exception("search_theaters failed")
        await interaction.followup.send(f"검색 실패: {e}")
        return
    if not matches:
        await interaction.followup.send(f"'{query}'에 해당하는 극장을 찾지 못했습니다.")
        return
    lines = ["**검색 결과**"] + [f"- {m['site_name']} ({m['site_no']})" for m in matches[:15]]
    await interaction.followup.send("\n".join(lines))


ALL_MOVIES = "__전체_영화__"  # 실제 영화 제목과 안 겹치는 sentinel 값


async def _finish_add(interaction, site, movie, date, grades, *, edit: bool):
    changed, target = add_target(site["site_no"], site["site_name"], grades, movie=movie, date=date)
    verb = "추가/변경됨" if changed else "변경 없음 (이미 동일하게 감시 중)"
    content = (
        f"**{target['site_name']}** ({target['site_no']}) - {describe_target(target)} [{verb}]"
    )
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
        movies = _distinct_sorted(entries, "prodNm")[:24]
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
        grades = _distinct_sorted(relevant, "tcscnsGradNm")

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
        entries = await fetch_showtimes_for_site(site["site_no"], date or None)
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


async def remove_autocomplete(interaction: discord.Interaction, current: str):
    targets = load_targets()
    choices = []
    for t in targets:
        if current in t["site_name"] or current in (t.get("movie") or "") or current in t["id"]:
            choices.append(
                app_commands.Choice(
                    name=f"{t['site_name']} - {describe_target(t)} [{t['id']}]",
                    value=t["id"],
                )
            )
    return choices[:25]


@tree.command(name="remove", description="감시 대상 제거", guild=GUILD)
@app_commands.describe(target="제거할 감시 대상 (자동완성에서 선택 권장)")
@app_commands.autocomplete(target=remove_autocomplete)
async def remove_cmd(interaction: discord.Interaction, target: str):
    targets = load_targets()
    matches = [t for t in targets if t["id"] == target]
    if not matches:
        matches = [
            t for t in targets if target in t["site_name"] or target in (t.get("movie") or "")
        ]

    if not matches:
        await interaction.response.send_message(
            f"'{target}'에 해당하는 감시 대상을 찾지 못했습니다.", ephemeral=True
        )
        return
    if len(matches) > 1:
        lines = [f"'{target}' 검색 결과가 여러 개입니다. 자동완성에서 선택해주세요:"]
        lines += [f"- [{t['id']}] {t['site_name']} - {describe_target(t)}" for t in matches]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    matched = matches[0]
    remove_target(matched["id"])
    await interaction.response.send_message(
        f"제거했습니다: {matched['site_name']} ({matched['id']}) - {describe_target(matched)}"
    )


@client.event
async def on_ready():
    if GUILD:
        await tree.sync(guild=GUILD)
    else:
        await tree.sync()
    msg = f"bot ready as {client.user}"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)
    logging.info(msg)


def run():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run()
