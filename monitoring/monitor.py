from dataclasses import dataclass, field

from alarm_bot.targets_store import TargetSpec
from cgv_open_push.cgv_models import CgvShowtime
from logging_setup import log_info

from .utils import build_signature


@dataclass
class Target:
    """감시 대상 하나. TargetSpec(감시 조건 자체)에 폴링 중 쌓이는 signature
    상태를 더한 것 — movie/date/grade 조건에 맞는 회차를 fetch.py가 만든
    스냅샷에서 찾아 이전 폴링과 비교하는 것까지 스스로 책임진다. CGV API나
    브라우저는 전혀 모른다 — fetch.py가 이미 정규화해서 넘겨준 CgvShowtime만
    다룬다."""

    id: str
    site_name: str
    movie: str
    dates: set[str]
    grades: set[str]
    provider: str = "cgv"
    previous_signatures: set[str] = field(default_factory=set)

    @classmethod
    def from_spec(cls, spec: TargetSpec) -> "Target":
        return cls(
            id=spec.id,
            site_name=spec.site_name,
            movie=spec.movie,
            dates=set(spec.date),
            grades=set(spec.grades),
            provider=spec.provider,
        )

    def matches(self, entry: CgvShowtime) -> bool:
        if entry.provider != self.provider:
            return False
        if entry.site_name != self.site_name:
            return False
        if self.dates and entry.date not in self.dates:
            return False
        if self.grades and (entry.grade or "") not in self.grades:
            return False
        if self.movie and self.movie not in entry.movie:
            return False
        return True

    def check(
        self,
        entries: list[CgvShowtime],
        *,
        baseline_only: bool,
    ) -> list[CgvShowtime]:
        """스냅샷 전체(여러 극장이 섞여 있음)에서 자기 조건에 맞는 회차 중 새로
        나타난 것을 반환하고, previous_signatures를 이번 폴링 결과로 갱신한다.
        baseline_only=True면 기준선만 잡고 new_entries는 항상 비운다 (첫 실행/방금
        추가된 대상 처리용)."""
        current_signatures: set[str] = set()
        new_entries: list[CgvShowtime] = []

        for entry in entries:
            if not self.matches(entry):
                continue

            signature = build_signature(entry)
            current_signatures.add(signature)

            if not baseline_only and signature not in self.previous_signatures:
                new_entries.append(entry)

        self.previous_signatures = current_signatures

        if new_entries:
            new_entries.sort(key=lambda entry: (entry.date, entry.time))
            log_info(f"{self.site_name} new showtimes: {len(new_entries)}")

        return new_entries


class TargetRegistry:
    """target id -> Target 인스턴스를 폴링 사이에 재사용한다. 이렇게 해야 이전
    폴링의 signature가 매번 새로 계산되지 않고 유지된다. targets.json이 바뀔
    때마다(추가/삭제) 최신 목록과 동기화하고, 방금 새로 생긴 대상인지도 여기서
    판단한다."""

    def __init__(self) -> None:
        self._targets: dict[str, Target] = {}

    def sync(self, specs: list[TargetSpec]) -> list[tuple[Target, bool]]:
        """(Target, is_new) 리스트를 반환한다. targets.json에서 사라진 대상은 정리한다."""
        live_ids = {spec.id for spec in specs}
        self._targets = {
            target_id: target
            for target_id, target in self._targets.items()
            if target_id in live_ids
        }

        result = []
        for spec in specs:
            is_new = spec.id not in self._targets
            if is_new:
                self._targets[spec.id] = Target.from_spec(spec)
            result.append((self._targets[spec.id], is_new))
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
