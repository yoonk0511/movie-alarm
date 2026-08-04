import logging
from datetime import datetime

import discord
from discord import app_commands
from playwright.async_api import async_playwright

from config import BOOKING_PAGE_URL, CO_CD, DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, LOG_FILE
from targets_store import add_target, load_targets, remove_target
from utils import get_base_url

logging.basicConfig(
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

GUILD = discord.Object(id=int(DISCORD_GUILD_ID)) if DISCORD_GUILD_ID else None

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


async def search_theaters(query):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            base_url=get_base_url(BOOKING_PAGE_URL),
        )
        page = await context.new_page()
        await page.goto(BOOKING_PAGE_URL, timeout=30000, wait_until="networkidle")
        response = await context.request.get(
            "/api/v1/booking/searchRegnList",
            params={"coCd": CO_CD},
            headers={"Accept": "application/json"},
            timeout=30000,
        )
        if not response.ok:
            await browser.close()
            raise RuntimeError(f"CGV API request failed: status={response.status}")
        result = await response.json()
        await browser.close()

    matches = []
    for region in result.get("data") or []:
        for site in region.get("siteList") or []:
            if query in site["siteNm"]:
                matches.append({"site_no": site["siteNo"], "site_name": site["siteNm"]})
    return matches


def grades_from_flags(imax, dx4, screenx, general, premium):
    flags = {
        "아이맥스": imax,
        "4DX": dx4,
        "SCREENX": screenx,
        "일반": general,
        "프리미엄관": premium,
    }
    return [name for name, on in flags.items() if on]


@tree.command(name="targets", description="현재 감시 중인 극장/등급 목록 조회", guild=GUILD)
async def targets_cmd(interaction: discord.Interaction):
    targets = load_targets()
    if not targets:
        await interaction.response.send_message("감시 중인 대상이 없습니다.")
        return
    lines = ["**현재 감시 대상**"]
    for t in targets:
        lines.append(f"- {t['site_name']} ({t['site_no']}): {', '.join(t['grades'])}")
    await interaction.response.send_message("\n".join(lines))


@tree.command(name="search", description="극장 이름으로 site_no 검색", guild=GUILD)
@app_commands.describe(query="검색할 극장 이름 (일부만 입력해도 됨)")
async def search_cmd(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        matches = await search_theaters(query)
    except Exception as e:
        await interaction.followup.send(f"검색 실패: {e}")
        return
    if not matches:
        await interaction.followup.send(f"'{query}'에 해당하는 극장을 찾지 못했습니다.")
        return
    lines = ["**검색 결과**"] + [f"- {m['site_name']} ({m['site_no']})" for m in matches[:15]]
    await interaction.followup.send("\n".join(lines))


@tree.command(name="add", description="감시 대상 추가", guild=GUILD)
@app_commands.describe(
    theater="추가할 극장 이름 (검색 결과가 하나로 좁혀지는 이름이어야 함)",
    imax="아이맥스",
    dx4="4DX",
    screenx="SCREENX",
    general="일반",
    premium="프리미엄관",
)
async def add_cmd(
    interaction: discord.Interaction,
    theater: str,
    imax: bool = False,
    dx4: bool = False,
    screenx: bool = False,
    general: bool = False,
    premium: bool = False,
):
    grades = grades_from_flags(imax, dx4, screenx, general, premium)
    if not grades:
        await interaction.response.send_message(
            "최소 하나 이상의 등급을 선택해야 합니다 (imax/dx4/screenx/general/premium).",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    try:
        matches = await search_theaters(theater)
    except Exception as e:
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
    changed, target = add_target(site["site_no"], site["site_name"], grades)
    verb = "추가/변경됨" if changed else "변경 없음 (이미 동일하게 감시 중)"
    await interaction.followup.send(
        f"**{target['site_name']}** ({target['site_no']}) - {', '.join(target['grades'])} [{verb}]"
    )


async def remove_autocomplete(interaction: discord.Interaction, current: str):
    targets = load_targets()
    return [
        app_commands.Choice(name=f"{t['site_name']} ({t['site_no']})", value=t["site_no"])
        for t in targets
        if current in t["site_name"]
    ][:25]


@tree.command(name="remove", description="감시 대상 제거", guild=GUILD)
@app_commands.describe(theater="제거할 극장 이름 (자동완성에서 선택 권장)")
@app_commands.autocomplete(theater=remove_autocomplete)
async def remove_cmd(interaction: discord.Interaction, theater: str):
    targets = load_targets()
    matches = [t for t in targets if t["site_no"] == theater or t["site_name"] == theater]
    if not matches:
        matches = [t for t in targets if theater in t["site_name"]]

    if not matches:
        await interaction.response.send_message(
            f"'{theater}'에 해당하는 감시 대상을 찾지 못했습니다.", ephemeral=True
        )
        return
    if len(matches) > 1:
        lines = [f"'{theater}' 검색 결과가 여러 개입니다:"]
        lines += [f"- {t['site_name']} ({t['site_no']})" for t in matches]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    target = matches[0]
    remove_target(target["site_no"])
    await interaction.response.send_message(f"제거했습니다: {target['site_name']} ({target['site_no']})")


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
