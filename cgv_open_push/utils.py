import re


def normalize_name(name: str) -> str:
    """이름 비교용. 띄어쓰기 유무로 매칭이 갈리지 않게 공백을 다 지운다
    (예: "씨네드쉐프 용산" == "씨네드쉐프용산")."""
    return re.sub(r"\s+", "", name)
