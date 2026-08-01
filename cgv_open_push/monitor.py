import json
import logging
import os
import time
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

from config import (
    BOOKING_PAGE_URL,
    BROWSER_REFRESH_INTERVAL_SEC,
    CO_CD,
    DISCORD_WEBHOOK_URL,
    LOG_FILE,
    POLL_INTERVAL_SEC,
    STATE_FILE,
    TARGETS,
)

logging.basicConfig(
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(message)s",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def log_info(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)
    logging.info(msg)


def log_error(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {msg}", flush=True)
    logging.error(msg)


def send_discord(content):
    if not DISCORD_WEBHOOK_URL:
        log_error("DISCORD_WEBHOOK_URL not set, skipping notification")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
    except Exception as e:
        log_error(f"failed to send discord message: {e}")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: set(v) for k, v in data.items()}
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({k: sorted(v) for k, v in state.items()}, f, ensure_ascii=False, indent=2)


def fetch_json(page, path):
    return page.evaluate(
        """
        async (path) => {
            const res = await fetch(path, { headers: { 'Accept': 'application/json' } });
            if (!res.ok) { throw new Error('http ' + res.status); }
            return await res.json();
        }
        """,
        path,
    )


def fetch_scheduled_dates(page, site_no):
    path = f"/api/v1/booking/searchSiteScnscYmdListBySite?coCd={CO_CD}&siteNo={site_no}"
    result = fetch_json(page, path)
    return [row["scnYmd"] for row in result.get("data") or []]


def fetch_showtimes(page, site_no, scn_ymd):
    path = (
        f"/api/v1/booking/searchMovScnInfo?coCd={CO_CD}&siteNo={site_no}"
        f"&scnYmd={scn_ymd}&rtctlScopCd=08"
    )
    result = fetch_json(page, path)
    return result.get("data") or []


def build_signature(entry):
    return "|".join(
        [
            entry["scnYmd"],
            entry["siteNo"],
            entry["scnsNm"],
            entry["scnsrtTm"],
            entry["prodNm"],
        ]
    )


def format_time(hhmm):
    return f"{hhmm[:2]}:{hhmm[2:4]}" if len(hhmm) >= 4 else hhmm


def format_date(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def check_target(page, target, state, first_run):
    site_no = target["site_no"]
    site_name = target["site_name"]
    grades = set(target["grades"])

    dates = fetch_scheduled_dates(page, site_no)
    current_signatures = set()
    new_entries = []

    for scn_ymd in dates:
        entries = fetch_showtimes(page, site_no, scn_ymd)
        for entry in entries:
            if entry.get("siteNo") != site_no:
                continue
            if entry.get("tcscnsGradNm") not in grades:
                continue
            sig = build_signature(entry)
            current_signatures.add(sig)
            if not first_run and sig not in state.get(site_no, set()):
                new_entries.append(entry)
        time.sleep(0.3)

    if new_entries:
        log_info(f"{site_name} new showtimes: {len(new_entries)}")
        new_entries.sort(key=lambda e: (e["scnYmd"], e["scnsrtTm"]))
        lines = [f"**{site_name} 예매 오픈 알림**"]
        for e in new_entries:
            lines.append(
                f"- {format_date(e['scnYmd'])} {format_time(e['scnsrtTm'])} "
                f"[{e['tcscnsGradNm']}] {e['prodNm']} ({e['scnsNm']})"
            )
        lines.append(BOOKING_PAGE_URL)
        send_discord("\n".join(lines))

    state[site_no] = current_signatures


def run():
    state = load_state()
    first_run = len(state) == 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        page = context.new_page()
        page.goto(BOOKING_PAGE_URL, timeout=30000, wait_until="networkidle")
        log_info("cgv-monitor started, browser session established")
        send_discord("cgv-monitor started...")

        last_refresh = time.time()

        while True:
            try:
                if time.time() - last_refresh > BROWSER_REFRESH_INTERVAL_SEC:
                    page.reload(timeout=30000, wait_until="networkidle")
                    last_refresh = time.time()
                    log_info("browser session refreshed")

                for target in TARGETS:
                    check_target(page, target, state, first_run)

                save_state(state)
                first_run = False
            except Exception as e:
                log_error(f"poll failed, will retry: {e}")
                try:
                    page.reload(timeout=30000, wait_until="networkidle")
                    last_refresh = time.time()
                except Exception as e2:
                    log_error(f"browser recovery failed: {e2}")

            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    run()
