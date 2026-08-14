from dataclasses import dataclass, field
from typing import Any

from logging_setup import log_info

from .utils import build_signature


@dataclass
class Target:
    """감시 대상 하나. targets.json의 dict 한 줄에 대응하며, movie/date/grade 조건에
    맞는 회차를 fetch.py가 만든 스냅샷에서 찾아 이전 폴링과 비교하는 것까지 스스로
    책임진다. CGV API나 브라우저는 전혀 모른다 — fetch.py가 이미 정규화해서 넘겨준
    회차 dict(site_no/site_name/movie/grade/date/time/screen)만 다룬다."""

    id: str
    site_name: str
    movie: str
    dates: set[str]
    grades: set[str]
    provider: str = "cgv"
    previous_signatures: set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Target":
        return cls(
            id=str(data["id"]),
            site_name=str(data["site_name"]),
            movie=str(data.get("movie") or ""),
            dates={str(d) for d in (data.get("date") or [])},
            grades={str(g) for g in data["grades"]},
            provider=str(data.get("provider") or "cgv"),
        )

    def matches(self, entry: dict[str, Any]) -> bool:
        if str(entry.get("provider", "")) != self.provider:
            return False
        if str(entry.get("site_name", "")) != self.site_name:
            return False
        if self.dates and str(entry.get("date", "")) not in self.dates:
            return False
        if self.grades and str(entry.get("grade", "")) not in self.grades:
            return False
        if self.movie and self.movie not in str(entry.get("movie", "")):
            return False
        return True

    def check(
        self,
        entries: list[dict[str, Any]],
        *,
        baseline_only: bool,
    ) -> list[dict[str, Any]]:
        """스냅샷 전체(여러 극장이 섞여 있음)에서 자기 조건에 맞는 회차 중 새로
        나타난 것을 반환하고, previous_signatures를 이번 폴링 결과로 갱신한다.
        baseline_only=True면 기준선만 잡고 new_entries는 항상 비운다 (첫 실행/방금
        추가된 대상 처리용)."""
        current_signatures: set[str] = set()
        new_entries: list[dict[str, Any]] = []

        for entry in entries:
            if not self.matches(entry):
                continue

            signature = build_signature(entry)
            current_signatures.add(signature)

            if not baseline_only and signature not in self.previous_signatures:
                new_entries.append(entry)

        self.previous_signatures = current_signatures

        if new_entries:
            new_entries.sort(
                key=lambda entry: (
                    str(entry.get("date", "")),
                    str(entry.get("time", "")),
                )
            )
            log_info(f"{self.site_name} new showtimes: {len(new_entries)}")

        return new_entries


class TargetRegistry:
    """target id -> Target 인스턴스를 폴링 사이에 재사용한다. 이렇게 해야 이전
    폴링의 signature가 매번 새로 계산되지 않고 유지된다. targets.json이 바뀔
    때마다(추가/삭제) 최신 목록과 동기화하고, 방금 새로 생긴 대상인지도 여기서
    판단한다."""

    def __init__(self) -> None:
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
                self._targets[target_id] = Target.from_dict(data)
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
