import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# data/cgv인 이유는 지금 target 데이터가 전부 CGV 극장/등급 형식이라서 — 다른
# provider가 생기면 그때 data/<provider>로 나뉜다.
TARGETS_FILE = os.path.join(os.path.dirname(__file__), "../data/cgv/targets.json")

# targets.json이 없을 때 최초 1회 생성에 쓰이는 기본 감시 대상.
# site_name은 CGV 극장 이름(CgvTheaterClient가 여기서 site_no를 내부적으로 찾음),
# grades는 tcscnsGradNm 값. movie는 prodNm 부분일치 필터, date는 scnYmd(YYYYMMDD)
# 정확히 일치하는 날짜들의 리스트(여러 날짜 동시 감시 가능). movie가 빈 문자열이거나
# date가 빈 리스트면 무관(전체) 취급. id는 같은 site_name에 여러 감시를 걸 수 있게
# 하는 고유 키.
# 이후 감시 대상 변경은 봇의 /add, /remove 커맨드 또는 targets.json 직접 수정으로 한다.
DEFAULT_TARGETS = [
    {
        "id": "0013",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": [],
        "grades": ["아이맥스", "4DX", "SCREENX"],
    },
]
