# 주식 웹앱 — 기초 세팅 스캐폴드 설계

- 작성일: 2026-05-12
- 상태: 승인됨 (구현 계획 작성 대기)

## 목표

한국투자증권 OpenAPI(KIS) **모의투자** 환경에서 종목 현재가를 조회해 화면에 표시하는
end-to-end 스켈레톤을 만든다. 프론트엔드 Next.js 16(pnpm) ↔ 백엔드 FastAPI(uv),
단일 레포 `side/` 아래 `frontend/`와 `backend/`로 구성.

이번 범위는 "기초 세팅 테스트" — 실제 기능 흐름의 축소판으로 **현재가 조회 1개 경로만**
완성한다.

## 비목표 (YAGNI)

다음은 지금 만들지 않는다:

- 로그인 / 인증
- 데이터베이스
- 계좌 잔고 조회, 모의 매수/매도 주문
- 실시간 시세 (WebSocket)
- 차트
- docker-compose (나중에 추가 예정)
- git 초기화 (나중에 추가 예정 — 그래서 이 설계 문서는 지금은 커밋하지 않음)

## 폴더 구조

```
side/
├── README.md                 # 실행 방법
├── .gitignore                # 루트 한 곳에서 전부 무시: **/.env, **/.env.local,
│                             #   .venv/, node_modules/, __pycache__/, .next/ 등
├── docs/superpowers/specs/2026-05-12-kis-stock-web-scaffold-design.md
├── backend/
│   ├── .env.example          # KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL, KIS_ACCOUNT
│   ├── pyproject.toml        # uv 프로젝트
│   ├── uv.lock
│   ├── .python-version
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 앱 생성, CORS, 라우터 등록
│   │   ├── config.py         # pydantic-settings로 .env 로드
│   │   ├── kis_client.py     # KIS 토큰 발급·캐싱 + 현재가 호출 (httpx async)
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── stocks.py     # GET /api/health, GET /api/stocks/{code}/price
│   └── tests/
│       └── test_stocks.py    # KIS HTTP 응답을 모킹한 라우터 테스트
└── frontend/                 # pnpm create next-app (App Router / TS / Tailwind / ESLint)
    ├── .env.local.example    # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
    └── src/app/
        ├── page.tsx          # 종목코드 입력 → 현재가 카드 (클라이언트 컴포넌트)
        └── lib/api.ts        # FastAPI 호출 래퍼
```

## 백엔드 동작 (FastAPI, uv)

### config.py
`pydantic-settings`로 `.env` 로드:

- `KIS_APP_KEY` (필수)
- `KIS_APP_SECRET` (필수)
- `KIS_BASE_URL` (기본값 모의투자: `https://openapivts.koreainvestment.com:29443`)
- `KIS_ACCOUNT` (지금은 미사용, 잔고/주문 확장 대비 자리만 마련)

키가 비어 있어도 서버는 정상 기동한다. 실제 KIS 호출 시점에 명확한 오류를 반환한다.

### kis_client.py
httpx async 클라이언트 사용.

- `get_access_token()`
  - `POST {KIS_BASE_URL}/oauth2/tokenP` (body: `grant_type=client_credentials`, `appkey`, `appsecret`)
  - 응답 토큰을 **만료시각과 함께 메모리에 캐싱**한다. KIS 토큰은 약 24시간 유효하고
    분당 1회 발급 제한이 있으므로 캐싱이 필수다. 만료가 임박하면(예: 60초 이내) 재발급.
- `get_price(code: str)`
  - `GET {KIS_BASE_URL}/uapi/domestic-stock/v1/quoting/inquire-price`
  - 헤더: `authorization: Bearer <token>`, `appkey`, `appsecret`, `tr_id: FHKST01010100`,
    `custtype: P`
  - 쿼리: `fid_cond_mrkt_div_code=J`, `fid_input_iscd=<code>`
  - 응답 `output`에서 현재가·전일대비·등락률·거래량을 추출해 단순 dict로 반환:
    `{ "code", "price", "change", "change_rate", "volume" }`
  - KIS가 오류 응답을 주면 예외를 던지고, 라우터가 502로 변환.

### routers/stocks.py
- `GET /api/health` → `{ "status": "ok" }`
- `GET /api/stocks/{code}/price` → `kis_client.get_price(code)` 결과 그대로 반환.
  KIS 오류 시 `HTTPException(502, detail=...)`.

### main.py
- `FastAPI()` 생성
- CORS 미들웨어: `http://localhost:3000` 허용 (GET)
- `stocks` 라우터 include

### 테스트 (tests/test_stocks.py)
- `respx` (또는 monkeypatch)로 KIS의 `/oauth2/tokenP`와 `/inquire-price` HTTP 응답을
  가짜로 둔다. **실제 KIS 호출은 하지 않는다.**
- `GET /api/health`가 200 + `{"status":"ok"}` 반환 확인
- `GET /api/stocks/005930/price`가 200 + 기대 키들을 가진 JSON 반환 확인
- KIS 오류 응답일 때 502 반환 확인

## 프론트엔드 동작 (Next.js 16, pnpm)

- `pnpm create next-app` 으로 생성 (App Router / TypeScript / Tailwind / ESLint).
- `src/app/lib/api.ts`
  - `fetchPrice(code: string)` → `fetch(\`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/stocks/${code}/price\`)`
    결과를 타입과 함께 반환. 비-200이면 에러 throw.
- `src/app/page.tsx` (클라이언트 컴포넌트)
  - 종목코드 입력창 (기본값 `005930` — 삼성전자) + "조회" 버튼
  - 클릭 시 `fetchPrice` 호출 → 현재가·전일대비·등락률·거래량을 카드 형태로 표시
  - 로딩 상태와 에러 메시지 최소 처리
- `.env.local.example` 에 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

## 환경변수

### backend/.env.example
```
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_ACCOUNT=
```

사용자는 [KIS Developers 포털](https://apiportal.koreainvestment.com)에서 모의투자 신청 +
앱 등록 후 APP_KEY / APP_SECRET 를 발급받아 `backend/.env`에 채워야 실제 시세가 나온다.
키가 없어도 서버·프론트는 기동하며, 시세 조회 시 502로 안내한다.

### frontend/.env.local.example
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 실행 방법 (README에 기재)

- 백엔드: `cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000`
- 프론트: `cd frontend && pnpm install && pnpm dev` → http://localhost:3000
- 백엔드 테스트: `cd backend && uv run pytest`

## 보안 메모

`KIS_APP_SECRET`이 브라우저에 노출되면 안 되므로, 프론트엔드는 KIS를 직접 호출하지 않고
**항상 FastAPI를 경유**한다.

## 향후 확장 지점 (이번 범위 아님, 참고용)

- `KIS_ACCOUNT` + 잔고 조회 (`inquire-balance`, 모의투자 tr_id `VTTC8434R`)
- 모의 매수/매도 주문 (`order-cash`, tr_id `VTTC0802U` / `VTTC0801U`)
- docker-compose 로 양쪽 동시 기동
- git 초기화 및 이 설계 문서 커밋
