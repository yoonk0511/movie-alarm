import json
import os
import uuid

from cgv_open_push.config import DEFAULT_TARGETS, TARGETS_FILE


def load_targets():
    if not os.path.exists(TARGETS_FILE):
        save_targets(DEFAULT_TARGETS)
        return [dict(t) for t in DEFAULT_TARGETS]
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        targets = json.load(f)
    for t in targets:
        t.setdefault("id", t["site_name"])
        t.setdefault("movie", "")
        t.setdefault("date", [])
        if isinstance(t["date"], str):
            # 예전엔 date가 단일 문자열이었다. 빈 문자열은 "날짜 무관", 값이 있으면
            # 그 날짜 하나짜리 리스트로 취급해서 새 스키마로 옮겨온다.
            t["date"] = [t["date"]] if t["date"] else []
    return targets


def save_targets(targets):
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


def add_target(site_name, grades, movie="", date=None):
    """감시 대상을 추가한다. 같은 (site_name, movie) 조합이 이미 있으면 grades와
    date를 각각 합집합으로 합친다 (movie만 식별자, grades/date는 둘 다 누적되는
    필터). date는 감시할 날짜(YYYYMMDD) 리스트 — 비우면 날짜 무관. site_no는
    저장하지 않는다 — CgvTheaterClient가 site_name으로 그때그때 알아서 찾는다.
    Returns (changed, target).
    """
    date = set(date or [])

    targets = load_targets()
    for t in targets:
        if t["site_name"] == site_name and t.get("movie", "") == movie:
            merged_grades = sorted(set(t["grades"]) | set(grades))
            merged_dates = sorted(set(t.get("date") or []) | date)
            changed = merged_grades != sorted(t["grades"]) or merged_dates != sorted(
                t.get("date") or []
            )
            t["grades"] = merged_grades
            t["date"] = merged_dates
            if changed:
                save_targets(targets)
            return changed, t

    new_target = {
        "id": uuid.uuid4().hex[:8],
        "site_name": site_name,
        "movie": movie,
        "date": sorted(date),
        "grades": sorted(set(grades)),
    }
    targets.append(new_target)
    save_targets(targets)
    return True, new_target


def remove_target(target_id):
    targets = load_targets()
    remaining = [t for t in targets if t["id"] != target_id]
    if len(remaining) == len(targets):
        return False
    save_targets(remaining)
    return True
