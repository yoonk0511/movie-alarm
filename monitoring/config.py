import os

POLL_INTERVAL_SEC = 300  # 5분마다 새 날짜/스케줄 확인
BROWSER_REFRESH_INTERVAL_SEC = 1800  # 30분마다 페이지 새로고침 (Cloudflare 세션 갱신)

# 이 monitor 프로세스 자신의 폴링 상태(감지한 signature)를 담는다. logs/와
# 같은 패턴으로, 런타임 데이터는 코드 소유권과 무관하게 최상위 data/에 모은다.
# data/cgv인 이유는 지금 감시 대상이 전부 CGV라서 — 다른 provider가 생기면
# 그때 data/<provider>로 나뉜다.
STATE_FILE = os.path.join(os.path.dirname(__file__), "../data/cgv/state.json")

# fetch.py가 쓰고 match.py가 읽는 정규화된 회차 스냅샷. 이 파일이 fetch(브라우저로
# CGV 긁기)와 match(target 조건 비교) 두 프로세스를 잇는 유일한 연결점이다 — 서로
# 직접 통신하지 않으므로 한쪽이 죽어도 다른 쪽은 마지막 스냅샷으로 계속 동작한다.
SHOWTIMES_FILE = os.path.join(os.path.dirname(__file__), "../data/cgv/showtimes.json")
