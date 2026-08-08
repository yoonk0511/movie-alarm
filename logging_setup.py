import logging
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "cgv-monitor.log")


def configure() -> None:
    logging.basicConfig(
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(message)s",
    )


def log_info(message: str) -> None:
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}",
        flush=True,
    )
    logging.info(message)


def log_error(message: str) -> None:
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {message}",
        flush=True,
    )
    logging.error(message)


def log_exception(message: str) -> None:
    """except 블록 안에서만 호출: 콘솔에는 메시지만 찍고, 로그 파일에는 트레이스백까지 남긴다.
    운영 중 원인 불명 에러가 나면 메시지만으로는 어디서 터졌는지 알 수 없어서, 실제
    예외 상황(재시도 경로)에서는 log_error 대신 이걸 쓴다."""
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {message}",
        flush=True,
    )
    logging.exception(message)
