import json
import os

from config import DEFAULT_TARGETS, TARGETS_FILE


def load_targets():
    if not os.path.exists(TARGETS_FILE):
        save_targets(DEFAULT_TARGETS)
        return [dict(t) for t in DEFAULT_TARGETS]
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_targets(targets):
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


def add_target(site_no, site_name, grades):
    """감시 대상을 추가한다. 이미 있는 site_no면 grades를 합친다.
    Returns (changed, target).
    """
    targets = load_targets()
    for t in targets:
        if t["site_no"] == site_no:
            merged = sorted(set(t["grades"]) | set(grades))
            changed = merged != sorted(t["grades"])
            t["grades"] = merged
            t["site_name"] = site_name
            if changed:
                save_targets(targets)
            return changed, t

    new_target = {"site_no": site_no, "site_name": site_name, "grades": sorted(set(grades))}
    targets.append(new_target)
    save_targets(targets)
    return True, new_target


def remove_target(site_no):
    targets = load_targets()
    remaining = [t for t in targets if t["site_no"] != site_no]
    if len(remaining) == len(targets):
        return False
    save_targets(remaining)
    return True
