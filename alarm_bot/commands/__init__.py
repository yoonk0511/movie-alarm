# 서브모듈을 import하는 것 자체가 각 모듈의 @tree.command 데코레이터를 실행시켜
# 슬래시 커맨드를 등록한다 — 아래 import는 이름을 안 쓰더라도 이 side effect
# 때문에 필요하다.
from . import add, remove, search, targets  # noqa: F401
