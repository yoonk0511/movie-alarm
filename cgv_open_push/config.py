import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

# 이 모듈은 CGV API 클라이언트(cgv_api.py) 전용 값만 둔다. discord 설정은
# alarm_bot/config.py, targets.json 관련은 alarm_bot/config.py, 폴링 루프
# 설정(주기/state.json)은 monitoring/config.py에 있다.
CO_CD = "A420"

BOOKING_PAGE_URL = "https://cgv.co.kr/cnm/movieBook/cinema"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
