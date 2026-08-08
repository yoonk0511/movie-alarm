

from cgv_open_push.config import (
    BOOKING_PAGE_URL,
    CO_CD,
    DISCORD_BOT_TOKEN,
    DISCORD_GUILD_ID,
    LOG_FILE,
    USER_AGENT,
)


def test_discord_bot():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    client.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    from alarm_bot import client
    test_discord_bot()
