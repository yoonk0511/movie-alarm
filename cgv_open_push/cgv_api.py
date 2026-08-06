from typing import Any

from playwright.async_api import APIRequestContext

from cgv_models import CgvMovie, CgvTheater
from config import CO_CD
from utils import normalize_name


class CgvApiError(RuntimeError):
    pass


class CgvApiClient:
    """CGV 예매 API 공용 클라이언트. site_no와 무관한 조회(극장 목록, 전체 상영작
    목록)를 담당한다. 극장별 스케줄 조회는 CgvTheaterClient가 상속해서 처리한다."""

    def __init__(self, request: APIRequestContext, co_cd: str = CO_CD) -> None:
        self._request = request
        self._co_cd = co_cd

    async def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        response = await self._request.get(
            path,
            params=params,
            headers={"Accept": "application/json"},
            timeout=30_000,
        )

        if not response.ok:
            raise CgvApiError(
                f"CGV API request failed: status={response.status}, url={response.url}"
            )

        try:
            result = await response.json()
        except Exception as error:
            raise CgvApiError(f"CGV API returned invalid JSON: url={response.url}") from error

        if not isinstance(result, dict):
            raise CgvApiError(f"unexpected CGV API response type: {type(result).__name__}")

        return result

    async def fetch_regn_list(self) -> list[CgvTheater]:
        """지역별 극장 목록 (극장 검색용). 응답은 지역(region) 단위로 묶여 있고 각
        지역 안에 siteList가 있어서, 평탄화해서 CgvTheater 리스트로 반환한다."""
        result = await self._get_json("/api/v1/booking/searchRegnList", {"coCd": self._co_cd})

        theaters: list[CgvTheater] = []
        for region in result.get("data") or []:
            if not isinstance(region, dict):
                continue
            for site in region.get("siteList") or []:
                if isinstance(site, dict):
                    theaters.append(CgvTheater.from_api(site))

        return theaters

    async def fetch_movie_list(self) -> list[CgvMovie]:
        """CGV 전체 상영작 목록 (극장 무관, 예매율 순)."""
        result = await self._get_json(
            "/api/v1/booking/searchAtktTopPostrList",
            {"coCd": self._co_cd, "movNm": "", "div": "", "attrCd": ""},
        )

        data = result.get("data") or []

        return [CgvMovie.from_api(movie) for movie in data if isinstance(movie, dict)]


class CgvTheaterClient(CgvApiClient):
    """특정 극장 하나의 상영 스케줄 조회. site_no 대신 극장 이름으로 생성하면,
    site_no는 실제로 조회가 필요해지는 첫 호출 때 내부적으로 찾는다."""

    def __init__(self, request: APIRequestContext, site_name: str, co_cd: str = CO_CD) -> None:
        super().__init__(request, co_cd)
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
        result = await self._get_json(
            path="/api/v1/booking/searchSiteScnscYmdListBySite",
            params={"coCd": self._co_cd, "siteNo": site_no},
        )

        data = result.get("data") or []
        if not isinstance(data, list):
            raise CgvApiError("scheduled-date response data is not a list")

        return [str(row["scnYmd"]) for row in data if isinstance(row, dict) and row.get("scnYmd")]

    async def fetch_showtimes(self, scn_ymd: str) -> list[dict[str, Any]]:
        site_no = await self._resolve_site_no()
        result = await self._get_json(
            "/api/v1/booking/searchMovScnInfo",
            {
                "coCd": self._co_cd,
                "siteNo": site_no,
                "scnYmd": scn_ymd,
                "rtctlScopCd": "08",
            },
        )

        data = result.get("data") or []
        if not isinstance(data, list):
            raise CgvApiError("showtime response data is not a list")

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
    from utils import get_base_url

    SAMPLE_THEATER_NAME = "용산 아이파크몰"

    async def demo() -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(base_url=get_base_url(BOOKING_PAGE_URL))
            page = await context.new_page()
            # CGV는 Cloudflare 봇 차단이 있어서, API를 바로 호출하기 전에 실제
            # 페이지를 한 번 열어 세션(쿠키)을 확보해야 한다.
            await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")

            try:
                client = CgvApiClient(context.request)
                theaters = await client.fetch_regn_list()
                print(f"[fetch_regn_list] 극장 수: {len(theaters)}")
                for theater in theaters[:5]:
                    print(" -", theater.site_no, theater.site_name, theater.biz_status)

                movies = await client.fetch_movie_list()
                print(f"[fetch_movie_list] 전체 상영작 수: {len(movies)}")
                for movie in movies[:5]:
                    print(" -", movie.movie_name, f"{movie.booking_rate}%")

                theater_client = CgvTheaterClient(context.request, site_name=SAMPLE_THEATER_NAME)
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
