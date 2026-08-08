from cgv_open_push.utils import normalize_name


def test_normalize_name_strips_all_whitespace():
    assert normalize_name("씨네드쉐프 용산") == "씨네드쉐프용산"


def test_normalize_name_passes_through_already_normalized():
    assert normalize_name("용산아이파크몰") == "용산아이파크몰"
