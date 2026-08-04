import json
import os
import uuid

from config import DEFAULT_TARGETS, TARGETS_FILE


def load_targets():
    if not os.path.exists(TARGETS_FILE):
        save_targets(DEFAULT_TARGETS)
        return [dict(t) for t in DEFAULT_TARGETS]
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        targets = json.load(f)
    for t in targets:
        t.setdefault("id", t["site_no"])
        t.setdefault("movie", "")
        t.setdefault("date", "")
    return targets


def save_targets(targets):
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


def add_target(site_no, site_name, grades, movie="", date=""):
    """감시 대상을 추가한다. 같은 (site_no, movie, date) 조합이 이미 있으면 grades를 합친다.
    Returns (changed, target).
    """
    targets = load_targets()
    for t in targets:
        if t["site_no"] == site_no and t.get("movie", "") == movie and t.get("date", "") == date:
            merged = sorted(set(t["grades"]) | set(grades))
            changed = merged != sorted(t["grades"])
            t["grades"] = merged
            t["site_name"] = site_name
            if changed:
                save_targets(targets)
            return changed, t

    new_target = {
        "id": uuid.uuid4().hex[:8],
        "site_no": site_no,
        "site_name": site_name,
        "movie": movie,
        "date": date,
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
