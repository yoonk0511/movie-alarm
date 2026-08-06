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
