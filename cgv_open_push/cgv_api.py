"""CGV 예매 API 백엔드. monitor.py(폴링 감시)와 bot.py(디스코드 명령)가 이 모듈을
통해서만 CGV와 통신한다.

- CgvApiClient: 극장 무관 조회.
  fetch_regn_list()  -> 전체 극장 목록
  fetch_movie_list() -> 전체 상영작 목록 (예매율 순)
- CgvTheaterClient(site_name): 극장 하나의 스케줄 조회. site_no는 첫 호출 때
  site_name으로 내부적으로 찾아서 캐시한다.
  fetch_scheduled_dates()          -> 그 극장의 상영일 목록
  fetch_showtimes(scn_ymd)         -> 그 날짜의 상영 회차 목록
  fetch_showtime_entries(scn_ymd?) -> scn_ymd 생략 시 가장 가까운 상영일 기준
- 실패(HTTP 에러/JSON 파싱 실패/예상과 다른 응답 구조)는 전부 CgvApiError로 통일.
"""

import json
from typing import Any
from urllib.parse import urlencode

from playwright.async_api import Page

from cgv_models import CgvMovie, CgvTheater
from config import CO_CD
from utils import normalize_name

# page.evaluate(fn, arg)는 fn 소스를 그대로 실행하고 arg는 JSON 직렬화해서 넘길
# 뿐이라 문자열 조립·eval() 인젝션 경로가 없다 (url도 urlencode를 거쳐서 옴).
# APIRequestContext 대신 이 방식을 쓰는 이유는 클래스 docstring 참고.
_FETCH_JS = """async (url) => {
    const response = await fetch(url, { headers: { "Accept": "application/json" } });
    const body = await response.text();
    return { ok: response.ok, status: response.status, url: response.url, body };
}"""


class CgvApiError(RuntimeError):
    pass


class CgvApiClient:
    """CGV 예매 API 공용 클라이언트. site_no와 무관한 조회(극장 목록, 전체 상영작
    목록)를 담당한다. 극장별 스케줄 조회는 CgvTheaterClient가 상속해서 처리한다.

    API 호출은 Playwright의 APIRequestContext가 아니라 실제 페이지 안에서
    page.evaluate()로 fetch()를 실행해서 한다 — 페이지 자체가 만드는 요청과 똑같은
    모양(같은 세션/쿠키/출처)이라 WAF가 봇으로 구분하기 더 어렵다."""

    def __init__(self, page: Page, co_cd: str = CO_CD) -> None:
        self._page = page
        self._co_cd = co_cd

    async def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{path}?{urlencode(params)}"
        result = await self._page.evaluate(_FETCH_JS, url)

        if not result["ok"]:
            raise CgvApiError(
                f"CGV API request failed: status={result['status']}, url={result['url']}"
            )

        try:
            data = json.loads(result["body"])
        except json.JSONDecodeError as error:
            raise CgvApiError(f"CGV API returned invalid JSON: url={result['url']}") from error

        if not isinstance(data, dict):
            raise CgvApiError(f"unexpected CGV API response type: {type(data).__name__}")

        return data

    async def _get_data_list(self, path: str, params: dict[str, str], what: str) -> list[Any]:
        result = await self._get_json(path, params)
        data = result.get("data") or []
        if not isinstance(data, list):
            raise CgvApiError(f"{what} response data is not a list")
        return data

    async def fetch_regn_list(self) -> list[CgvTheater]:
        """지역별 극장 목록 (극장 검색용). 응답은 지역(region) 단위로 묶여 있고 각
        지역 안에 siteList가 있어서, 평탄화해서 CgvTheater 리스트로 반환한다."""
        data = await self._get_data_list(
            "/api/v1/booking/searchRegnList", {"coCd": self._co_cd}, what="region-list"
        )

        theaters: list[CgvTheater] = []
        for region in data:
            if not isinstance(region, dict):
                continue
            for site in region.get("siteList") or []:
                if isinstance(site, dict):
                    theaters.append(CgvTheater.from_api(site))

        return theaters

    async def fetch_movie_list(self) -> list[CgvMovie]:
        """CGV 전체 상영작 목록 (극장 무관, 예매율 순)."""
        data = await self._get_data_list(
            "/api/v1/booking/searchAtktTopPostrList",
            {"coCd": self._co_cd, "movNm": "", "div": "", "attrCd": ""},
            what="movie-list",
        )

        return [CgvMovie.from_api(movie) for movie in data if isinstance(movie, dict)]


class CgvTheaterClient(CgvApiClient):
    """특정 극장 하나의 상영 스케줄 조회. site_no 대신 극장 이름으로 생성하면,
    site_no는 실제로 조회가 필요해지는 첫 호출 때 내부적으로 찾는다."""

    def __init__(self, page: Page, site_name: str, co_cd: str = CO_CD) -> None:
        super().__init__(page, co_cd)
        self.site_name = site_name
        self._site_no: str | None = None

    async def _resolve_site_no(self) -> str:
        if self._site_no is not None:
            return self._site_no

        theaters = await self.fetch_regn_list()
        query = normalize_name(self.site_name)
        matches = [theater for theater in theaters if query in normalize_name(theater.site_name)]
        exact = [theater for theater in matches if normalize_name(theater.site_name) == query]
        if exact:
            matches = exact

        if not matches:
            raise CgvApiError(f"no theater matches name: {self.site_name!r}")
        if len(matches) > 1:
            names = [theater.site_name for theater in matches]
            raise CgvApiError(f"ambiguous theater name {self.site_name!r}: {names}")

        self._site_no = matches[0].site_no
        return self._site_no

    async def fetch_scheduled_dates(self) -> list[str]:
        site_no = await self._resolve_site_no()
        data = await self._get_data_list(
            "/api/v1/booking/searchSiteScnscYmdListBySite",
            {"coCd": self._co_cd, "siteNo": site_no},
            what="scheduled-date",
        )

        return [str(row["scnYmd"]) for row in data if isinstance(row, dict) and row.get("scnYmd")]

    async def fetch_showtimes(self, scn_ymd: str) -> list[dict[str, Any]]:
        site_no = await self._resolve_site_no()
        data = await self._get_data_list(
            "/api/v1/booking/searchMovScnInfo",
            {
                "coCd": self._co_cd,
                "siteNo": site_no,
                "scnYmd": scn_ymd,
                "rtctlScopCd": "08",
            },
            what="showtime",
        )

        return [entry for entry in data if isinstance(entry, dict)]

    async def fetch_showtime_entries(self, scn_ymd: str | None = None) -> list[dict[str, Any]]:
        """scn_ymd를 안 주면 가장 가까운 상영일 기준."""
        if scn_ymd is None:
            dates = await self.fetch_scheduled_dates()
            if not dates:
                return []
            scn_ymd = dates[0]

        return await self.fetch_showtimes(scn_ymd)


if __name__ == "__main__":
    # 실제 CGV API에 붙는 수동 스모크 테스트. pytest 목(mock) 테스트는
    # tests/test_cgv_api.py 참고 — 여기는 눈으로 직접 확인하고 싶을 때 실행.
    import asyncio

    from playwright.async_api import async_playwright
    from config import BOOKING_PAGE_URL

    SAMPLE_THEATER_NAME = "용산 아이파크몰"

    async def demo() -> None:
        async with async_playwright() as playwright:
            # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다
            # (일반 브라우저는 막히지 않는 것 확인함). 서버 배포 시엔 Xvfb 등 가상
            # 디스플레이가 필요하다.
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            # CGV는 Cloudflare 봇 차단이 있어서, API를 바로 호출하기 전에 실제
            # 페이지를 한 번 열어 세션(쿠키)을 확보해야 한다.
            await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")

            try:
                client = CgvApiClient(page)
                theaters = await client.fetch_regn_list()
                print(f"[fetch_regn_list] 극장 수: {len(theaters)}")
                for theater in theaters[:5]:
                    print(" -", theater.site_no, theater.site_name, theater.biz_status)

                movies = await client.fetch_movie_list()
                print(f"[fetch_movie_list] 전체 상영작 수: {len(movies)}")
                for movie in movies[:5]:
                    print(" -", movie.movie_name, f"{movie.booking_rate}%")

                theater_client = CgvTheaterClient(page, site_name=SAMPLE_THEATER_NAME)
                dates = await theater_client.fetch_scheduled_dates()
                print(f"[fetch_scheduled_dates] {SAMPLE_THEATER_NAME}: {dates}")

                entries = await theater_client.fetch_showtime_entries()
                print(f"[fetch_showtime_entries] 가장 가까운 날짜 상영 회차: {len(entries)}개")
                for entry in entries:
                    print(
                        " -",
                        entry.get("prodNm"),
                        entry.get("tcscnsGradNm"),
                        entry.get("scnsrtTm"),
                    )
            finally:
                await browser.close()

    asyncio.run(demo())
