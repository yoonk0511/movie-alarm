# cgv-open-push (개인용)

CGV IMAX/4DX/SCREENX 등 예매 오픈을 감지해서 Discord로 알림만 보내는 스크립트.
예매 자체는 자동화하지 않음 — 알림을 받고 직접 클릭해서 예매해야 함.

감시 대상(극장/등급)은 Discord 봇의 슬래시 커맨드로 실행 중에 조회·추가·삭제할 수 있다
(`monitor.py`는 알림만 보내는 프로세스, `bot.py`는 감시 대상을 관리하는 별도 프로세스).

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

설정값은 프로젝트 루트의 `.env` 파일로 관리한다 (`.env.example`을 복사해서 채우면 됨).
`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않는다 — 절대 하드코딩하거나 커밋하지 말 것.

```bash
cp .env.example .env
```

### 알림 (webhook)

1. Discord 채널에서 "연동 > 웹후크 만들기"로 웹훅 URL 발급
2. `.env`에 설정:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

3. 감시할 극장/관 조합은 최초 실행 시 `config.py`의 `DEFAULT_TARGETS`를 기준으로
   `targets.json`이 생성된다 (기본값: 용산아이파크몰 IMAX/4DX/SCREENX). 이후로는
   `targets.json`이 실제 감시 대상이며, 아래 봇의 `/add` `/remove`로 관리한다.

### 감시 대상 관리 봇 (선택)

`/targets` `/add` `/remove` 슬래시 커맨드로 감시 대상을 조회·변경하려면 별도의
Discord 봇 애플리케이션이 필요하다 (웹훅과는 별개).

1. https://discord.com/developers/applications → New Application
2. **Bot** 탭 → 토큰 발급 → `DISCORD_BOT_TOKEN`. Privileged Gateway Intents는 전부 꺼도 됨
   (슬래시 커맨드만 쓰므로 메시지 내용 읽기 권한 불필요)
3. **OAuth2 → URL Generator** → Scopes에서 `bot`, `applications.commands` 체크,
   Bot Permissions에서 `Send Messages`, `View Channels`, `Use Slash Commands` 체크 →
   생성된 URL로 서버에 봇 초대
4. Discord 설정 → 고급 → 개발자 모드 켜기 → 서버 아이콘 우클릭 → ID 복사 → `DISCORD_GUILD_ID`
   (길드에 바로 등록해야 슬래시 커맨드가 즉시 반영됨. 전역 등록은 최대 1시간 소요)

`.env`에 설정:

```
DISCORD_BOT_TOKEN=...
DISCORD_GUILD_ID=...
```

## 실행

두 프로세스는 독립적으로 실행하며, `targets.json`을 통해서만 상태를 공유한다
(`monitor.py`는 읽기만, `bot.py`는 쓰기만 한다).

```bash
python3 monitor.py   # 알림 감시 루프
python3 bot.py        # 슬래시 커맨드 봇 (감시 대상 관리를 안 쓸 거면 생략 가능)
```

계속 떠 있어야 하는 프로세스이므로, 터미널을 닫아도 유지하려면 `nohup`이나
`launchd`(macOS) 같은 걸로 백그라운드/데몬화해서 돌리는 걸 권장.

```bash
nohup python3 monitor.py > /dev/null 2>&1 &
nohup python3 bot.py > /dev/null 2>&1 &
```

## 봇 커맨드

- `/targets` — 현재 감시 중인 극장/영화/날짜/등급 목록 조회 (각 항목의 id도 같이 표시)
- `/search query:<극장 이름>` — 극장 이름으로 CGV 사이트 코드(site_no) 검색
- `/add theater:<극장 이름> movie:<영화 제목> date:<YYYYMMDD> imax:<bool> dx4:<bool> screenx:<bool> general:<bool> premium:<bool>` —
  극장 이름 검색 결과가 하나로 좁혀지면 감시 대상에 추가.
  `movie`는 영화 제목 부분일치, `date`는 특정 날짜만 감시 (둘 다 비우면 전체 대상).
  등급도 하나도 안 고르면 등급 무관으로 감시.
  같은 극장에 (movie, date) 조합이 다르면 별도 감시 대상으로 추가되어, 한 극장에서
  여러 영화/날짜를 동시에 감시할 수 있음. 같은 조합이 이미 있으면 선택한 등급만 합침
- `/remove target:<자동완성으로 선택 또는 극장/영화 이름>` — 감시 대상에서 제거

`/add`, `/remove`는 각각 `targets.json`을 바꾸며, `monitor.py`는 매 폴링(기본 5분)마다
`targets.json`을 다시 읽으므로 재시작 없이 반영된다. 새로 추가한 대상은 추가 시점의
스케줄을 기준선으로만 잡고, 그 다음 폴링부터 새로 열리는 회차만 알림을 보낸다.

## 참고

- 알림에는 예매 페이지 링크만 들어감 (`https://cgv.co.kr/cnm/movieBook/cinema`).
  CGV 사이트가 SPA라 극장을 URL로 바로 지정하는 딥링크는 안 되고, 알림 클릭 후
  극장 목록에서 원하는 극장을 직접 선택해야 함.
- `state.json`에 마지막으로 확인한 상영회차 스냅샷이 감시 대상 id별로 저장됨. 처음 실행
  시에는 기존 스케줄을 기준선으로만 저장하고 알림은 보내지 않음. 감시 대상에서 제거된
  항목의 state는 다음 폴링 때 정리되어, 나중에 다시 추가하면 새로 기준선을 잡는다.
- Cloudflare 세션(쿠키)이 만료될 수 있어 30분마다 페이지를 새로고침해서 세션을 갱신함.
  봇의 `/search`, `/add`는 커맨드 실행 시마다 별도의 짧은 브라우저 세션을 새로 띄운다.
