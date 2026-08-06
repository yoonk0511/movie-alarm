import asyncio
from typing import Any

from cgv_api import CgvTheaterClient
from utils import build_signature, log_info


class TargetFilter:
    """감시 대상(target) 하나의 movie/date/grade 조건으로 상영 회차를 걸러내고,
    이전 폴링 대비 새로 나타난 회차를 가려낸다. 극장 스코프는 CgvTheaterClient가
    site_name으로 이미 잡아주므로, 여기서는 movie/date/grade만 본다."""

    def __init__(self, target: dict[str, Any]) -> None:
        self.grades = {str(grade) for grade in target["grades"]}
        self.movie = str(target.get("movie") or "")
        self.date = str(target.get("date") or "")

    def matches_date(self, scn_ymd: str) -> bool:
        return not self.date or str(scn_ymd) == self.date

    def matches_entry(self, entry: dict[str, Any]) -> bool:
        if self.grades and str(entry.get("tcscnsGradNm", "")) not in self.grades:
            return False
        if self.movie and self.movie not in str(entry.get("prodNm", "")):
            return False
        return True

    def split_new_entries(
        self,
        entries: list[dict[str, Any]],
        previous_signatures: set[str],
        *,
        baseline_only: bool,
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """조건에 맞는 entries 중 새로 나타난 것들과, 이번 폴링의 signature 전체를
        반환한다. baseline_only=True면 이번 폴링은 기준선만 잡고 new_entries는
        항상 비운다 (첫 실행/방금 추가된 대상 처리용)."""
        new_entries: list[dict[str, Any]] = []
        current_signatures: set[str] = set()

        for entry in entries:
            if not self.matches_entry(entry):
                continue

            signature = build_signature(entry)
            current_signatures.add(signature)

            if not baseline_only and signature not in previous_signatures:
                new_entries.append(entry)

        return new_entries, current_signatures


async def check_target(
    theater: CgvTheaterClient,
    target: dict[str, Any],
    state: dict[str, set[str]],
    first_run: bool,
) -> list[dict[str, Any]]:
    """감시 대상 하나를 폴링해서 새로 나타난 상영 회차를 반환한다 (없으면 빈 리스트).
    state는 이번 폴링 결과로 갱신하지만, 알림 전송은 호출부(run.py) 책임이다."""
    target_id = str(target["id"])
    site_name = str(target["site_name"])
    target_filter = TargetFilter(target)

    # 새로 추가된(state에 아직 없는) 대상은 이번 폴링을 기준선으로만 저장하고
    # 알림은 보내지 않는다 (첫 실행 때 first_run과 동일한 취급).
    target_is_new = target_id not in state
    previous_signatures = state.get(target_id, set())
    baseline_only = first_run or target_is_new

    current_signatures: set[str] = set()
    new_entries: list[dict[str, Any]] = []

    scheduled_dates = await theater.fetch_scheduled_dates()

    for scn_ymd in scheduled_dates:
        if not target_filter.matches_date(scn_ymd):
            continue

        entries = await theater.fetch_showtimes(scn_ymd)

        date_new_entries, date_signatures = target_filter.split_new_entries(
            entries, previous_signatures, baseline_only=baseline_only
        )
        new_entries.extend(date_new_entries)
        current_signatures |= date_signatures

        await asyncio.sleep(0.3)

    state[target_id] = current_signatures

    if new_entries:
        new_entries.sort(
            key=lambda entry: (
                str(entry.get("scnYmd", "")),
                str(entry.get("scnsrtTm", "")),
            )
        )
        log_info(f"{site_name} new showtimes: {len(new_entries)}")

    return new_entries
