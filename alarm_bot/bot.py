import logging
from datetime import datetime

from logging_setup import configure

from . import commands  # noqa: F401  각 커맨드 모듈을 등록시키는 side-effect import
from .config import DISCORD_BOT_TOKEN
from .discord_client import GUILD, client, tree

configure()


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
