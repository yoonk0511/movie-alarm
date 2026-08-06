import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")

CO_CD = "A420"

# targets.json이 없을 때 최초 1회 생성에 쓰이는 기본 감시 대상.
# site_name은 CGV 극장 이름(CgvTheaterClient가 여기서 site_no를 내부적으로 찾음),
# grades는 tcscnsGradNm 값. movie는 prodNm 부분일치 필터, date는 scnYmd(YYYYMMDD)
# 정확히 일치 필터. 둘 다 빈 문자열이면 무관(전체) 취급. id는 같은 site_name에
# 여러 감시를 걸 수 있게 하는 고유 키.
# 이후 감시 대상 변경은 봇의 /add, /remove 커맨드 또는 targets.json 직접 수정으로 한다.
DEFAULT_TARGETS = [
    {
        "id": "0013",
        "site_name": "용산아이파크몰",
        "movie": "",
        "date": "",
        "grades": ["아이맥스", "4DX", "SCREENX"],
    },
]

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "cgv-monitor.log")

BOOKING_PAGE_URL = "https://cgv.co.kr/cnm/movieBook/cinema"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
