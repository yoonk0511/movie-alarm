from bot import grades_from_flags


def test_grades_from_flags_all_false_returns_empty():
    assert grades_from_flags(False, False, False, False, False) == []


def test_grades_from_flags_selects_only_flagged_grades():
    result = grades_from_flags(imax=True, dx4=False, screenx=True, general=False, premium=False)
    assert result == ["아이맥스", "SCREENX"]


def test_grades_from_flags_all_true_preserves_declared_order():
    result = grades_from_flags(True, True, True, True, True)
    assert result == ["아이맥스", "4DX", "SCREENX", "일반", "프리미엄관"]
