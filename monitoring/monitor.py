import asyncio
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

from cgv_open_push.cgv_api import CgvTheaterClient
from logging_setup import log_info

from .utils import build_signature


@dataclass
class Target:
    """감시 대상 하나. targets.json의 dict 한 줄에 대응하며, movie/date/grade 조건에
    맞는 회차를 실제 CGV 데이터에서 찾아 이전 폴링과 비교하는 것까지 스스로 책임진다.
    호출부는 dict을 파싱하거나 site_no/이전 signature를 따로 다루지 않는다."""

    id: str
    site_name: str
    movie: str
    dates: set[str]
    grades: set[str]
    theater: CgvTheaterClient
    previous_signatures: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict[str, Any], page: Page) -> "Target":
        return cls(
            id=str(data["id"]),
            site_name=str(data["site_name"]),
            movie=str(data.get("movie") or ""),
            dates={str(d) for d in (data.get("date") or [])},
            grades={str(g) for g in data["grades"]},
            theater=CgvTheaterClient(page, site_name=str(data["site_name"])),
        )

    def matches_date(self, scn_ymd: str) -> bool:
        return not self.dates or str(scn_ymd) in self.dates

    def matches_entry(self, entry: dict[str, Any]) -> bool:
        if self.grades and str(entry.get("tcscnsGradNm", "")) not in self.grades:
            return False
        if self.movie and self.movie not in str(entry.get("prodNm", "")):
            return False
        return True

    async def check(self, *, baseline_only: bool) -> list[dict[str, Any]]:
        """실제 CGV 데이터를 가져와 자기 조건에 맞는 회차 중 새로 나타난 것을 반환하고,
        자신의 previous_signatures를 이번 폴링 결과로 갱신한다. baseline_only=True면
        이번 폴링은 기준선만 잡고 new_entries는 항상 비운다 (첫 실행/방금 추가된
        대상 처리용)."""
        current_signatures: set[str] = set()
        new_entries: list[dict[str, Any]] = []

        scheduled_dates = await self.theater.fetch_scheduled_dates()

        for scn_ymd in scheduled_dates:
            if not self.matches_date(scn_ymd):
                continue

            entries = await self.theater.fetch_showtimes(scn_ymd)

            for entry in entries:
                if not self.matches_entry(entry):
                    continue

                signature = build_signature(entry)
                current_signatures.add(signature)

                if not baseline_only and signature not in self.previous_signatures:
                    new_entries.append(entry)

            await asyncio.sleep(0.3)

        self.previous_signatures = current_signatures

        if new_entries:
            new_entries.sort(
                key=lambda entry: (
                    str(entry.get("scnYmd", "")),
                    str(entry.get("scnsrtTm", "")),
                )
            )
            log_info(f"{self.site_name} new showtimes: {len(new_entries)}")

        return new_entries


class TargetRegistry:
    """target id -> Target 인스턴스를 폴링 사이에 재사용한다. 이렇게 해야
    CgvTheaterClient의 site_no 캐시와 이전 폴링 signature가 폴링마다 새로
    계산되지 않고 유지된다. targets.json이 바뀔 때마다(추가/삭제) 최신 목록과
    동기화하고, 방금 새로 생긴 대상인지도 여기서 판단한다."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._targets: dict[str, Target] = {}

    def sync(self, target_dicts: list[dict[str, Any]]) -> list[tuple[Target, bool]]:
        """(Target, is_new) 리스트를 반환한다. targets.json에서 사라진 대상은 정리한다."""
        live_ids = {str(data["id"]) for data in target_dicts}
        self._targets = {
            target_id: target
            for target_id, target in self._targets.items()
            if target_id in live_ids
        }

        result = []
        for data in target_dicts:
            target_id = str(data["id"])
            is_new = target_id not in self._targets
            if is_new:
                self._targets[target_id] = Target.from_dict(data, self._page)
            result.append((self._targets[target_id], is_new))
        return result

    def restore_signatures(self, state: dict[str, list[str]]) -> None:
        for target_id, signatures in state.items():
            if target_id in self._targets:
                self._targets[target_id].previous_signatures = set(signatures)

    def signatures_snapshot(self) -> dict[str, list[str]]:
        return {
            target_id: sorted(target.previous_signatures)
            for target_id, target in self._targets.items()
        }


if __name__ == "__main__":
    # 실제 CGV API에 붙는 수동 스모크 테스트. 대상 여러 개를 동시에 다루는 것과,
    # 극장을 못 찾는 대상 하나가 다른 대상에 영향을 주지 않는 것까지 확인한다
    # (pytest 목 테스트는 tests/test_monitor.py 참고).
    from playwright.async_api import async_playwright

    from cgv_open_push.config import BOOKING_PAGE_URL

    SAMPLE_TARGETS = [
        {
            "id": "demo-1",
            "site_name": "용산아이파크몰",
            "movie": "오디세이",
            "date": [],
            "grades": ["아이맥스"],
        },
        {
            "id": "demo-2",
            "site_name": "동탄",
            "movie": "",
            "date": [],
            "grades": [],
        },
    ]

    async def demo() -> None:
        async with async_playwright() as playwright:
            # headless=True는 CGV WAF에 헤드리스로 탐지되어 403이 나서 False로 둔다.
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(BOOKING_PAGE_URL, timeout=30_000, wait_until="networkidle")

            try:
                registry = TargetRegistry(page)

                print("-- 첫 실행 (여러 대상 동시 처리, 기준선만 잡음) --")
                for target, is_new in registry.sync(SAMPLE_TARGETS):
                    baseline = await target.check(baseline_only=True)
                    print(
                        f"[{target.site_name}] is_new={is_new} "
                        f"new_entries={len(baseline)}개 "
                        f"signature 수={len(target.previous_signatures)}"
                    )

                print("-- 재실행 (변화 없어야 함) --")
                for target, _is_new in registry.sync(SAMPLE_TARGETS):
                    unchanged = await target.check(baseline_only=False)
                    print(f"[{target.site_name}] new_entries={len(unchanged)}개")

                print("-- signature 하나 지워서 '새로 생긴 회차' 시뮬레이션 --")
                first_target, _ = registry.sync(SAMPLE_TARGETS)[0]
                if first_target.previous_signatures:
                    first_target.previous_signatures.pop()
                    simulated = await first_target.check(baseline_only=False)
                    print(f"[{first_target.site_name}] new_entries={len(simulated)}개")
                    for entry in simulated[:3]:
                        print(
                            " -",
                            entry.get("prodNm"),
                            entry.get("tcscnsGradNm"),
                            entry.get("scnsrtTm"),
                        )

                print("-- 존재하지 않는 극장 이름 (개별 실패가 격리되는지 확인) --")
                bad_target = Target.from_dict(
                    {
                        "id": "demo-bad",
                        "site_name": "존재하지않는극장이름",
                        "movie": "",
                        "date": [],
                        "grades": [],
                    },
                    page,
                )
                try:
                    await bad_target.check(baseline_only=True)
                except Exception as error:
                    print(f"[존재하지않는극장이름] 예상대로 실패 (다른 대상엔 영향 없음): {error}")
            finally:
                await browser.close()

    asyncio.run(demo())
