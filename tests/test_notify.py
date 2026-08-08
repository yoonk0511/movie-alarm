from unittest.mock import MagicMock

import requests

from alarm_bot.notify import send_discord


def test_send_discord_skips_when_webhook_url_empty(monkeypatch):
    post_mock = MagicMock()
    monkeypatch.setattr(requests, "post", post_mock)

    send_discord("", "hello")

    post_mock.assert_not_called()


def test_send_discord_posts_content_to_webhook(monkeypatch):
    response = MagicMock()
    post_mock = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "post", post_mock)

    send_discord("https://discord.com/api/webhooks/x", "hello")

    args, kwargs = post_mock.call_args
    assert args[0] == "https://discord.com/api/webhooks/x"
    assert kwargs["json"] == {"content": "hello"}
    response.raise_for_status.assert_called_once()


def test_send_discord_swallows_request_errors(monkeypatch):
    def raise_error(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "post", raise_error)

    send_discord("https://discord.com/api/webhooks/x", "hello")  # should not raise


def test_send_discord_swallows_http_error_status(monkeypatch):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("400")
    monkeypatch.setattr(requests, "post", MagicMock(return_value=response))

    send_discord("https://discord.com/api/webhooks/x", "hello")  # should not raise
