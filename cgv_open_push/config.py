import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")

CO_CD = "A420"

# tcscnsGradNm 값으로 쓸 수 있는 상영관 등급
VALID_GRADES = ["아이맥스", "4DX", "SCREENX", "일반", "프리미엄관"]

# targets.json이 없을 때 최초 1회 생성에 쓰이는 기본 감시 대상.
# site_no는 CGV 극장 코드, grades는 tcscnsGradNm 값.
# 이후 감시 대상 변경은 봇의 /add, /remove 커맨드 또는 targets.json 직접 수정으로 한다.
DEFAULT_TARGETS = [
    {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "grades": ["아이맥스", "4DX", "SCREENX"],
    },
]

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
TARGETS_FILE = os.path.join(os.path.dirname(__file__), "targets.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "cgv-monitor.log")

BOOKING_PAGE_URL = "https://cgv.co.kr/cnm/movieBook/cinema"
