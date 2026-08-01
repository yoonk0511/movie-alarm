import os

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

CO_CD = "A420"

# 감시할 극장/관 목록. site_no는 CGV 극장 코드, grades는 tcscnsGradNm 값
# (아이맥스 / 4DX / SCREENX / 일반 / 프리미엄관 등)
TARGETS = [
    {
        "site_no": "0013",
        "site_name": "용산아이파크몰",
        "grades": ["아이맥스", "4DX", "SCREENX"],
    },
]

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
LOG_FILE = os.path.join(os.path.dirname(__file__), "cgv-monitor.log")

BOOKING_PAGE_URL = "https://cgv.co.kr/cnm/movieBook/cinema"
