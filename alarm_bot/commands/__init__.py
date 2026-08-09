from .add import add_cmd
from .remove import remove_cmd
from .search import search_cmd
from .targets import targets_cmd

# 현재 등록된 슬래시 커맨드 전체 목록 — 새 커맨드를 추가하면 여기도 같이 늘어난다.
# import 자체가 각 모듈의 @tree.command 데코레이터를 실행시켜 등록까지 끝낸다.
__all__ = [
    "add_cmd",
    "remove_cmd",
    "search_cmd",
    "targets_cmd",
]
