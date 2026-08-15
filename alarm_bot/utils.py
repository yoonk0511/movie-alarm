from contextlib import asynccontextmanager

from playwright.async_api import async_playwright

from cgv_open_push.cgv_api import CgvApiClient, CgvTheaterClient
from cgv_open_push.config import BOOKING_PAGE_URL, USER_AGENT
from monitoring.config import THEATERS_FILE
from monitoring.utils import load_theaters

ALL_MOVIES = "__전체_영화__"  # 실제 영화 제목과 안 겹치는 sentinel 값


@asynccontextmanager
async def cgv_browser_session():
    async with async_playwright() as p:
        # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다
        # (cgv_open_push/cgv_api.py 참고).
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        page = await context.new_page()
        await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")
        try:
            yield page
        finally:
            await browser.close()


async def search_theaters(query):
    """fetch.py가 하루 한 번 갱신하는 극장 목록 캐시에서 찾는다 — 매번 브라우저를
    새로 띄우지 않아서 즉시 응답한다. 캐시가 아직 없으면(첫 배포 직후 등) 그때만
    라이브로 조회한다."""
    theaters = load_theaters(THEATERS_FILE)

    if not theaters:
        async with cgv_browser_session() as page:
            theaters = [
                {"site_no": theater.site_no, "site_name": theater.site_name}
                for theater in await CgvApiClient(page).fetch_regn_list()
            ]

    return [
        {"site_no": theater["site_no"], "site_name": theater["site_name"]}
        for theater in theaters
        if query in theater["site_name"]
    ]


async def fetch_showtimes_for_site(site_name, scn_ymd=None):
    async with cgv_browser_session() as page:
        return await CgvTheaterClient(page, site_name=site_name).fetch_showtime_entries(scn_ymd)


def distinct_sorted(entries, field):
    return sorted({str(entry[field]) for entry in entries if entry.get(field)})


def describe_target(t):
    movie_desc = t.get("movie") or "전체 영화"
    date_desc = ", ".join(t["date"]) if t.get("date") else "전체 날짜"
    grade_desc = ", ".join(t["grades"]) if t["grades"] else "등급 무관"
    return f"{movie_desc} / {date_desc} / {grade_desc}"
