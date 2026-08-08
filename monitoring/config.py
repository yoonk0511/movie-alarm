import os

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

# 이 monitor 프로세스 자신의 폴링 상태(감지한 signature)를 담는다 — CGV API
# 자체와는 무관해서 cgv_open_push가 아니라 여기 둔다.
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
