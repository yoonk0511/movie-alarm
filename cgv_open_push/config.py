import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

# discord 관련 설정(토큰/길드ID/웹훅)은 전부 alarm_bot/config.py로 옮겼다 —
# 여기는 CGV provider 전용 값만 둔다.
CO_CD = "A420"

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

# TARGETS_FILE/DEFAULT_TARGETS는 alarm_bot/config.py로 옮겼다 — targets.json을
# 실제로 읽고 쓰는 targets_store.py가 거기 있다 (bot이 /add, /remove로 관리).
# state.json은 이 monitor 프로세스 자신의 폴링 상태(감지한 signature)라 provider인
# 여기 그대로 둔다.
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

BOOKING_PAGE_URL = "https://cgv.co.kr/cnm/movieBook/cinema"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
