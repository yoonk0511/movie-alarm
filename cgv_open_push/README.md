# cgv-open-push (개인용)

용산아이파크몰 CGV IMAX/4DX/SCREENX 예매 오픈을 감지해서 Discord로 알림만 보내는 스크립트.
예매 자체는 자동화하지 않음 — 알림을 받고 직접 클릭해서 예매해야 함.

## 동작 방식

CGV 사이트(cgv.co.kr)는 Cloudflare 봇 차단이 걸려 있어 단순 HTTP 요청으로는 API를 호출할 수 없다.
그래서 Playwright로 실제 헤드리스 브라우저 세션을 하나 띄워두고, 그 세션 안에서
`fetch()`로 CGV 내부 API(`/api/v1/booking/...`)를 호출하는 방식으로 우회한다.

5분마다:
1. `searchSiteScnscYmdListBySite` — 극장에 스케줄이 열려있는 날짜 목록 조회
2. 각 날짜에 대해 `searchMovScnInfo` — 실제 상영시간표 조회, IMAX/4DX/SCREENX만 필터링
3. 이전 폴링과 비교해서 새로 추가된 상영회차가 있으면 Discord 웹훅으로 알림

## 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 설정

1. Discord 채널에서 "연동 > 웹후크 만들기"로 웹훅 URL 발급
2. 환경변수로 설정:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

3. `config.py`의 `TARGETS`에서 감시할 극장/관 조합 수정 (기본값: 용산아이파크몰 IMAX/4DX/SCREENX)

## 실행

```bash
python3 monitor.py
```

계속 떠 있어야 하는 프로세스이므로, 터미널을 닫아도 유지하려면 `nohup`이나
`launchd`(macOS) 같은 걸로 백그라운드/데몬화해서 돌리는 걸 권장.

```bash
nohup python3 monitor.py > /dev/null 2>&1 &
```

## 참고

- 알림에는 예매 페이지 링크만 들어감 (`https://cgv.co.kr/cnm/movieBook/cinema`).
  CGV 사이트가 SPA라 극장을 URL로 바로 지정하는 딥링크는 안 되고, 알림 클릭 후
  극장 목록에서 "용산아이파크몰"을 직접 선택해야 함.
- `state.json`에 마지막으로 확인한 상영회차 스냅샷이 저장됨. 처음 실행 시에는
  기존 스케줄을 기준선으로만 저장하고 알림은 보내지 않음.
- Cloudflare 세션(쿠키)이 만료될 수 있어 30분마다 페이지를 새로고침해서 세션을 갱신함.
