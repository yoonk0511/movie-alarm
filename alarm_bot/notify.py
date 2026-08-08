import requests

from logging_setup import log_error


def send_discord(webhook_url: str, content: str) -> None:
    if not webhook_url:
        log_error("DISCORD_WEBHOOK_URL not set, skipping notification")
        return

    try:
        response = requests.post(
            webhook_url,
            json={"content": content},
            timeout=10,
        )
        response.raise_for_status()

    except requests.RequestException as error:
        log_error(f"failed to send discord message: {error}")
