import asyncio
from unittest.mock import MagicMock

import monitoring.fetch as fetch_module
from monitoring.fetch import fetch_all_showtimes


def run(coro):
    return asyncio.run(coro)


class FakeTheaterClient:
    def __init__(self, page, site_name):
        self.site_name = site_name

    async def fetch_scheduled_dates(self):
        return []


def test_fetch_all_showtimes_reuses_theater_client_across_calls(monkeypatch):
    monkeypatch.setattr(fetch_module, "target_site_names", lambda: ["용산아이파크몰"])
    monkeypatch.setattr(fetch_module, "CgvTheaterClient", FakeTheaterClient)

    theater_clients = {}
    page = MagicMock()

    run(fetch_all_showtimes(page, theater_clients))
    first_client = theater_clients["용산아이파크몰"]
    run(fetch_all_showtimes(page, theater_clients))

    assert theater_clients["용산아이파크몰"] is first_client


def test_fetch_all_showtimes_drops_clients_for_targets_no_longer_watched(monkeypatch):
    site_names = ["용산아이파크몰"]
    monkeypatch.setattr(fetch_module, "target_site_names", lambda: site_names)
    monkeypatch.setattr(fetch_module, "CgvTheaterClient", FakeTheaterClient)

    theater_clients = {}
    page = MagicMock()

    run(fetch_all_showtimes(page, theater_clients))
    assert "용산아이파크몰" in theater_clients

    site_names.clear()
    run(fetch_all_showtimes(page, theater_clients))

    assert theater_clients == {}
