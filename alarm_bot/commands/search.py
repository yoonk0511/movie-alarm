import logging

import discord
from discord import app_commands

from ..discord_client import GUILD, tree
from ..utils import search_theaters


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
    lines = ["**검색 결과**"] + [f"- {m.site_name} ({m.site_no})" for m in matches[:15]]
    await interaction.followup.send("\n".join(lines))
