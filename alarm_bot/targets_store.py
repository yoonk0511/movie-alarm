import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from monitoring.utils import atomic_write_json

from .config import DEFAULT_TARGETS, TARGETS_FILE


@dataclass
class TargetSpec:
    """감시 대상 하나의 저장된 스펙. targets.json의 항목 하나에 대응한다 —
    monitoring/monitor.py의 Target은 이 스펙에 폴링 중 쌓이는 signature 상태를
    더한 것."""

    id: str
    site_name: str
    movie: str = ""
    date: list[str] = field(default_factory=list)
    grades: list[str] = field(default_factory=list)
    provider: str = "cgv"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetSpec":
        date = data.get("date") or []
        if isinstance(date, str):
            # 예전엔 date가 단일 문자열이었다. 빈 문자열은 "날짜 무관", 값이 있으면
            # 그 날짜 하나짜리 리스트로 취급해서 새 스키마로 옮겨온다.
            date = [date] if date else []

        return cls(
            id=str(data.get("id") or data["site_name"]),
            site_name=str(data["site_name"]),
            movie=str(data.get("movie") or ""),
            date=[str(d) for d in date],
            grades=[str(g) for g in (data.get("grades") or [])],
            provider=str(data.get("provider") or "cgv"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "site_name": self.site_name,
            "movie": self.movie,
            "date": self.date,
            "grades": self.grades,
            "provider": self.provider,
        }


def load_targets() -> list[TargetSpec]:
    if not os.path.exists(TARGETS_FILE):
        save_targets([TargetSpec.from_dict(t) for t in DEFAULT_TARGETS])
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [TargetSpec.from_dict(t) for t in raw]


def save_targets(targets: list[TargetSpec]) -> None:
    atomic_write_json(TARGETS_FILE, [t.to_dict() for t in targets])


def add_target(
    site_name: str,
    grades: list[str],
    movie: str = "",
    date: list[str] | None = None,
    provider: str = "cgv",
) -> tuple[bool, TargetSpec]:
    """감시 대상을 추가한다. 같은 (provider, site_name, movie) 조합이 이미 있으면
    grades와 date를 각각 합집합으로 합친다 (movie만 식별자, grades/date는 둘 다
    누적되는 필터). date는 감시할 날짜(YYYYMMDD) 리스트 — 비우면 날짜 무관.
    provider는 나중에 CGV 말고 다른 곳이 생겼을 때 구분용 — 지금은 항상 "cgv".
    site_no는 저장하지 않는다 — CgvTheaterClient가 site_name으로 그때그때 알아서
    찾는다.
    Returns (changed, target).
    """
    wanted_dates = set(date or [])

    targets = load_targets()
    for t in targets:
        if t.site_name == site_name and t.movie == movie and t.provider == provider:
            merged_grades = sorted(set(t.grades) | set(grades))
            merged_dates = sorted(set(t.date) | wanted_dates)
            changed = merged_grades != sorted(t.grades) or merged_dates != sorted(t.date)
            t.grades = merged_grades
            t.date = merged_dates
            if changed:
                save_targets(targets)
            return changed, t

    new_target = TargetSpec(
        id=uuid.uuid4().hex[:8],
        site_name=site_name,
        movie=movie,
        date=sorted(wanted_dates),
        grades=sorted(set(grades)),
        provider=provider,
    )
    targets.append(new_target)
    save_targets(targets)
    return True, new_target


def remove_target(target_id: str) -> bool:
    targets = load_targets()
    remaining = [t for t in targets if t.id != target_id]
    if len(remaining) == len(targets):
        return False
    save_targets(remaining)
    return True
