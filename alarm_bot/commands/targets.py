import discord

from ..discord_client import GUILD, tree
from ..targets_store import load_targets
from ..utils import describe_target


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
        lines.append(f"- [{t['id']}] {t['site_name']} - {describe_target(t)}")
    await interaction.response.send_message("\n".join(lines))
