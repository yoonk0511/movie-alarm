from contextlib import asynccontextmanager

from playwright.async_api import async_playwright

from cgv_open_push.cgv_api import CgvApiClient, CgvTheaterClient
from cgv_open_push.cgv_models import CgvMovie, CgvTheater
from cgv_open_push.config import BOOKING_PAGE_URL, USER_AGENT
from monitoring.config import MOVIES_FILE, SHOWTIMES_FILE, THEATERS_FILE
from monitoring.utils import load_json_list, load_showtimes

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


async def search_theaters(query: str) -> list[CgvTheater]:
    """fetch.py가 하루 한 번 갱신하는 극장 목록 캐시에서 찾는다 — 매번 브라우저를
    새로 띄우지 않아서 즉시 응답한다. 캐시가 아직 없으면(첫 배포 직후 등) 그때만
    라이브로 조회한다."""
    theaters = load_json_list(THEATERS_FILE, CgvTheater)

    if not theaters:
        async with cgv_browser_session() as page:
            theaters = await CgvApiClient(page).fetch_regn_list()

    return [theater for theater in theaters if query in theater.site_name]


async def search_movies(query: str) -> list[CgvMovie]:
    """fetch.py가 하루 한 번 갱신하는 전체 상영작 목록 캐시(극장 무관)에서
    찾는다. 캐시가 아직 없으면 그때만 라이브로 조회한다."""
    movies = load_json_list(MOVIES_FILE, CgvMovie)

    if not movies:
        async with cgv_browser_session() as page:
            movies = await CgvApiClient(page).fetch_movie_list()

    return [movie for movie in movies if query in movie.movie_name]


def search_grades(query: str, site_name: str = "") -> list[str]:
    """CGV 전체 등급/포맷 목록을 주는 API가 따로 없어서, fetch.py가 5분마다 갱신하는
    showtimes 스냅샷에서 실제로 관측된 값들로 찾는다 — target이 하나도 없으면
    빈 목록. site_name이 주어지면 그 극장 회차로 좁혀서 찾는다 — 아직 극장을
    안 골랐거나(비어있음) 그 극장 회차가 스냅샷에 없으면 전체에서 찾는다."""
    entries = load_showtimes(SHOWTIMES_FILE)
    if site_name:
        scoped = [entry for entry in entries if entry.site_name == site_name]
        if scoped:
            entries = scoped
    grades = sorted({entry.grade for entry in entries if entry.grade})
    return [grade for grade in grades if query in grade]


async def fetch_showtimes_for_site(site_name, scn_ymd=None):
    async with cgv_browser_session() as page:
        return await CgvTheaterClient(page, site_name=site_name).fetch_showtime_entries(scn_ymd)


def distinct_movies(showtimes) -> list[str]:
    return sorted({showtime.movie for showtime in showtimes if showtime.movie})


def distinct_grades(showtimes) -> list[str]:
    return sorted({showtime.grade for showtime in showtimes if showtime.grade})


def describe_target(target):
    movie_desc = target.movie or "전체 영화"
    date_desc = ", ".join(target.date) if target.date else "전체 날짜"
    grade_desc = ", ".join(target.grades) if target.grades else "등급 무관"
    return f"{movie_desc} / {date_desc} / {grade_desc}"
