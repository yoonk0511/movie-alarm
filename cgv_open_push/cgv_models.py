from dataclasses import dataclass
from typing import Any


@dataclass
class CgvTheater:
    # 예시: {'coCd': 'A420', 'siteNo': '0056', 'siteNm': '강남', 'bzplcOperStusNm': '운영중',
    #        'distance': None, 'movkndCd': None}
    co_cd: str
    site_no: str
    site_name: str
    biz_status: str | None = None
    distance: float | None = None
    movie_kind_cd: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "CgvTheater":
        return cls(
            co_cd=str(data.get("coCd", "")),
            site_no=str(data.get("siteNo", "")),
            site_name=str(data.get("siteNm", "")),
            biz_status=data.get("bzplcOperStusNm"),
            distance=data.get("distance"),
            movie_kind_cd=data.get("movkndCd"),
        )


@dataclass
class CgvMovie:
    # 예시: {'coCd': 'A420', 'movNo': '30001323', 'movNm': '오디세이', 'i320Fnm': '30001323_320.jpg',
    #        'scnBssTm': '172', 'cratgClsCd': '02', 'atktRate': '51.46', 'mblUrl': None}
    co_cd: str
    movie_no: str
    movie_name: str
    running_time_min: str | None = None
    rating_cd: str | None = None
    booking_rate: str | None = None
    poster_file_name: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "CgvMovie":
        return cls(
            co_cd=str(data.get("coCd", "")),
            movie_no=str(data.get("movNo", "")),
            movie_name=str(data.get("movNm", "")),
            running_time_min=data.get("scnBssTm"),
            rating_cd=data.get("cratgClsCd"),
            booking_rate=data.get("atktRate"),
            poster_file_name=data.get("i320Fnm"),
        )


@dataclass
class CgvShowtime:
    """정규화된 상영 회차 하나. monitoring 쪽(fetch/match)이 다루는 공용 스키마라,
    다른 provider(예: megabox)가 생기면 그쪽도 이 필드 이름으로 맞춰 내보내야 한다
    — provider 필드로 어느 쪽에서 온 회차인지 구분한다. site_name은 응답에
    없어서(요청 자체가 이미 그 극장으로 scoped) 호출부가 넘겨준다."""

    site_no: str
    site_name: str
    movie: str
    grade: str | None
    date: str
    time: str
    screen: str | None
    provider: str = "cgv"

    @classmethod
    def from_api(cls, data: dict[str, Any], site_name: str) -> "CgvShowtime":
        return cls(
            site_no=str(data.get("siteNo", "")),
            site_name=site_name,
            movie=str(data.get("prodNm", "")),
            grade=data.get("tcscnsGradNm"),
            date=str(data.get("scnYmd", "")),
            time=str(data.get("scnsrtTm", "")),
            screen=data.get("scnsNm"),
        )
