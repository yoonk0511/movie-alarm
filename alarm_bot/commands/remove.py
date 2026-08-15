import discord
from discord import app_commands

from ..discord_client import GUILD, tree
from ..targets_store import load_targets, remove_target
from ..utils import describe_target


async def remove_autocomplete(interaction: discord.Interaction, current: str):
    targets = load_targets()
    choices = []
    for t in targets:
        if current in t.site_name or current in t.movie or current in t.id:
            choices.append(
                app_commands.Choice(
                    name=f"{t.site_name} - {describe_target(t)} [{t.id}]",
                    value=t.id,
                )
            )
    return choices[:25]


@tree.command(name="remove", description="감시 대상 제거", guild=GUILD)
@app_commands.describe(target="제거할 감시 대상 (자동완성에서 선택 권장)")
@app_commands.autocomplete(target=remove_autocomplete)
async def remove_cmd(interaction: discord.Interaction, target: str):
    targets = load_targets()
    matches = [t for t in targets if t.id == target]
    if not matches:
        matches = [t for t in targets if target in t.site_name or target in t.movie]

    if not matches:
        await interaction.response.send_message(
            f"'{target}'에 해당하는 감시 대상을 찾지 못했습니다.", ephemeral=True
        )
        return
    if len(matches) > 1:
        lines = [f"'{target}' 검색 결과가 여러 개입니다. 자동완성에서 선택해주세요:"]
        lines += [f"- [{t.id}] {t.site_name} - {describe_target(t)}" for t in matches]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    matched = matches[0]
    remove_target(matched.id)
    await interaction.response.send_message(
        f"제거했습니다: {matched.site_name} ({matched.id}) - {describe_target(matched)}"
    )
