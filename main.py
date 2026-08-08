from alarm_bot.config import  DISCORD_BOT_TOKEN

def discord_test():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    client.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    from alarm_bot.bot import client
    discord_test()
