import discord
from discord import app_commands

from .config import DISCORD_GUILD_ID

GUILD = discord.Object(id=int(DISCORD_GUILD_ID)) if DISCORD_GUILD_ID else None

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
