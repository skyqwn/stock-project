# 종목 LLM 챗봇 서비스 — 설계 문서

- 작성일: 2026-05-13
- 작성: /office-hours (gstack) 세션
- 모드: Builder (포트폴리오 / 이직 준비용 프로젝트)
- 상태: DRAFT — 사용자 검토 대기

## 목표 / 맥락

프론트엔드 개발자가 이직 준비용으로 만드는 풀스택 포트폴리오 프로젝트.
"LangGraph로 LLM 에이전트 챗봇을 만들 줄 안다" + "FastAPI 백엔드(인증·DB·외부 API 연동)도 한다"를
보여주는 것이 핵심. 프론트는 이미 강점이므로 깔끔하게만, 무게는 백엔드 + LLM 쪽.

성공 기준: **작아도 끝까지 동작하고 배포까지 된 결과물.** 채용담당자 관점에서 반쯤 만든 거대한
플랫폼보다 완성도 높은 작은 것이 낫다. 이력서에 라이브 링크를 걸 수 있어야 한다.

기존 토대: `side/` 레포에 Next.js 16(pnpm) + FastAPI(uv) 스캐폴드, `/api/health`,
`/api/stocks/{code}/price`(KIS 모의투자 현재가 조회), 백엔드 pytest 11개 통과.

## 무엇을 만드나 (전체 그림)

로그인한 사용자에게 **모든 페이지 우측 하단에 플로팅 챗 버튼**(`position: fixed`)이 떠 있고,
누르면 챗 패널이 슬라이드로 열린다(인터콤/채널톡 형태). 자연어로 종목에 대해 물어보면
**LangGraph 에이전트**가 도구를 호출해 실시간 KIS 데이터를 가져오고 한국어로 설명·분석해준다.
챗 위젯은 **현재 페이지를 컨텍스트로 주입**한다 — 종목 페이지(`/stocks/005930`)에 있으면 그
종목을 인지하고, 일반 페이지면 일반 챗. 나중 단계에서 챗에서 모의 매수/매도, 뉴스 검색, 다종목 대시보드.

"LangGraph로 만들 가치"의 핵심 = 단순히 프롬프트에 데이터 때려넣고 LLM 한 번 호출이 아니라,
**LLM이 어떤 도구를 언제 호출할지 판단하고 여러 단계로 추론하는 에이전트**여야 한다. 그리고
프론트에서 **에이전트가 지금 무슨 도구를 호출 중인지 표시**("삼성전자 시세 조회 중…")하는 것이
"진짜 에이전트 짰네"로 보이게 하는 포인트.

## 비목표 (이번 설계 범위에서 제외 / 나중)

- 실시간 시세 WebSocket
- 정교한 기술적 분석 / 백테스팅
- 다중 LLM 프로바이더 추상화 (OpenAI로 고정)
- 모바일 앱
- 결제 / 구독
- **장기/대화 간 사용자 메모리 (mem0 / langmem / LangGraph Store)** — "이 사용자는 반도체 선호, 보수적 추천 선호" 같은 사실을 여러 대화에 걸쳐 기억. 멋진 추가지만 범위 늘어남. 단계 4 후보로 보류. (이번 범위의 "메모리"는 (a) 대화 내 기억뿐 — 아래 단계 3 참고)

## 기술 스택 (확정)

| 레이어 | 선택 | 비고 |
|---|---|---|
| 프론트 | Next.js 16, pnpm, App Router, TS, Tailwind v4 | 이미 스캐폴드됨 |
| 백엔드 | FastAPI, uv, Python 3.12 | 이미 스캐폴드됨. 사용자: NestJS 경험有, FastAPI는 가벼운 CRUD만 — 문법 익히는 중 |
| DB | PostgreSQL + SQLAlchemy **Core** (async) | `create_async_engine` + `text()` 생SQL. ORM 미사용. 밑에 `asyncpg` 드라이버 |
| 토큰 스토어 | Redis | refresh token 보관 + 로테이션/무효화 |
| 인증 | 자체 JWT (FastAPI) | access token은 `Authorization: Bearer`, refresh token은 Redis. 사용자가 NestJS에서 해본 패턴 |
| LLM 에이전트 | LangGraph + OpenAI | 도구 호출 기반 에이전트, 답변 스트리밍 |
| 대화 기억 | LangGraph **Postgres 체크포인터** (`langgraph-checkpoint-postgres`) | thread_id별 그래프 상태(메시지 히스토리) 영구 저장. 단계 3부터. Redis 체크포인터도 가능하지만 휘발성이라 대화 히스토리엔 Postgres가 적합 |
| 외부 데이터 | 한국투자증권 OpenAPI(모의투자) | 기존 `backend/app/kis_client.py` 확장 |
| 마이그레이션 | alembic 또는 번호 붙인 `.sql` 파일 (단계 1에서 확정) | ORM 안 쓰므로 모델 기반 자동생성은 안 함 — `text()` SQL과 수기 마이그레이션 |

## 빌드 순서 (단계)

각 단계는 독립적으로 동작·배포 가능한 결과물. 단계 1만으로도 포트폴리오 항목 성립.

### 단계 1 — 인증 토대 (로그인 + DB + Redis)
사용자가 "처음부터 사용자 있는 상태로 짓고 싶다"고 해서 이걸 먼저. 단, **최소로** 해서 빨리
챗봇으로 넘어간다.
- Postgres 연결(SQLAlchemy Core async 엔진), `users` 테이블, 마이그레이션 1개.
- Redis 연결.
- 회원가입(`POST /api/auth/register`) — 비밀번호 해싱(argon2 또는 bcrypt).
- 로그인(`POST /api/auth/login`) — access JWT 발급(짧은 만료) + refresh token 생성해 Redis에 저장.
- 토큰 갱신(`POST /api/auth/refresh`) — Redis의 refresh token 검증 → 로테이션(기존 무효화, 새로 발급).
- 로그아웃(`POST /api/auth/logout`) — Redis에서 refresh token 삭제.
- 인증 의존성(`Depends`) — access JWT 검증해 현재 사용자 주입. 보호된 라우트에 적용.
- 프론트: 로그인/회원가입 페이지, 토큰 저장(httpOnly 쿠키 권장 또는 메모리+refresh), 인증된 fetch 래퍼, 보호된 라우트 가드.
- 테스트: 인증 플로우(가입→로그인→갱신→로그아웃, 만료/위조 토큰) — Redis는 fakeredis 또는 테스트 인스턴스, DB는 테스트 DB.

### 단계 2 — LangGraph 챗봇 코어 ← **포트폴리오의 주인공**
- 백엔드: LangGraph 그래프. 도구 2~3개로 시작:
  - `get_price(code)` — 기존 `kis_client.get_price` 래핑
  - `get_company_info(code)` — KIS 기본정보(종목명, 시총 등)
  - `get_daily_chart(code, period)` — KIS 일봉 (최근 추세)
  - 그래프 흐름: LLM이 질문 읽고 → 필요한 도구 판단 → 호출(여러 번 가능) → 받은 데이터로 한국어 답변 작성
- 답변 스트리밍: FastAPI `StreamingResponse`/SSE로 토큰 + "도구 호출 중" 이벤트를 프론트로.
- 보호된 엔드포인트(`POST /api/chat`, 인증 필요). 대화는 단계 2에선 아직 영구 저장 안 함 — 인메모리 체크포인터(`MemorySaver`)로 한 요청 흐름 내 멀티턴만. 영구 저장은 단계 3에서 Postgres 체크포인터로 교체.
- 프론트: **전역 플로팅 챗 위젯** — 루트 레이아웃에 우측 하단 `position: fixed` 버튼, 클릭하면 챗 패널 슬라이드. 현재 라우트를 보고 종목 페이지면 그 종목 코드를 컨텍스트로 챗 API에 같이 보냄(`/api/chat` 요청 body에 `context: { stock_code }`). 토큰 스트리밍 렌더, **에이전트 단계 표시 UI**("삼성전자 시세 조회 중…"), 로딩/에러.
- **단계 2 끝나면 배포** — 프론트 Vercel, 백엔드 Fly.io 또는 Render, Postgres·Redis는 매니지드(예: Render Postgres + Upstash Redis). 이력서에 라이브 링크.
- 테스트: LangGraph 도구들(KIS 모킹), 챗 엔드포인트 인증·스트리밍 동작.

### 단계 3 — 대화 기억(영구) + 모의 매매
- **대화 기억 (= "메모리" 의 (a) 대화 내 기억):** LangGraph 체크포인터를 인메모리에서 **Postgres 체크포인터**로 교체. `thread_id`는 `user:{user_id}:conv:{conv_id}` 형태로 사용자에 묶음 → 로그아웃/재로그인해도 같은 사용자면 같은 thread_id 재구성 → 히스토리 그대로 로드(로그아웃은 토큰만 만료, 서버 데이터 무관). 추가로 가벼운 `conversations` 테이블(id, user_id, title, created_at)을 둬서 UI에서 대화 목록 보여줌(실제 메시지 상태는 체크포인터가 보관). 장기/대화 간 메모리(mem0 등 (b))는 비목표 — 단계 4 후보.
- KIS 모의투자 주문: `kis_client`에 `place_order`(매수/매도, tr_id VTTC0802U/VTTC0801U), `get_balance`(VTTC8434R) 추가. `.env`의 `KIS_ACCOUNT` 사용.
- 에이전트에 `place_order` / `get_balance` 도구 추가 → "삼성전자 10주 사줘" → 에이전트가 **확인 받고** 모의 주문. 위험한 동작이므로 명시적 confirm 단계.
- 프론트: 챗 히스토리 목록(과거 대화 다시 열기), 주문 확인 UI, 잔고 패널.

### 단계 4 — 뉴스 검색 / 분석 고도화
- 뉴스 검색 도구 추가 — Tavily 또는 네이버 검색 API. 에이전트가 최근 뉴스 가져와 답변에 인용/요약.
- (선택) 다종목 대시보드, 간단한 차트 컴포넌트.

## 검토했던 갈림길과 선택

- **챗봇 먼저 vs 로그인+DB 먼저** → 로그인+DB 먼저 (사용자 선택). 트레이드오프: 포트폴리오 쇼피스(챗봇)가 늦어지고 인증에서 시간 소모 위험. 완화책: 단계 1을 최소로, 단계 2 끝나면 즉시 배포.
- **DB: SQLAlchemy Core vs asyncpg 직접** → SQLAlchemy Core async (사용자가 이미 `create_async_engine` 패턴 사용 경험). 연결 풀·트랜잭션 공짜, 쿼리는 `text()` 생SQL.
- **인증: 자체 FastAPI JWT vs NextAuth(Auth.js)** → 자체 JWT + Redis refresh token (사용자가 NestJS에서 해본 패턴, 백엔드 역량 더 보여줌). 주의: 직접 만드는 인증은 실수 나기 쉬운 영역 — refresh 로테이션·만료·해싱 꼼꼼히, 테스트로 커버.
- **LLM: OpenAI 고정 vs 추상화** → OpenAI 고정 (YAGNI).
- **챗 UI: 종목 페이지 전용 패널 vs 전역 플로팅 위젯** → 전역 플로팅 위젯 (모든 페이지 우측 하단 fixed 버튼, 인터콤 형태). 현재 페이지를 컨텍스트로 챗 API에 주입.
- **대화 기억 백엔드: Redis 체크포인터 vs Postgres 체크포인터** → Postgres (영구 보존돼야 하는 데이터. Redis는 휘발성이라 — RDB/AOF로 영속 가능하지만 본령이 아님 — refresh token 전용). LangGraph 체크포인터는 thread_id 키잉이라 로그아웃과 무관하게 사용자별 히스토리 유지.
- **메모리 범위: (a) 대화 내 기억만 vs + (b) mem0 장기 기억** → (a)만 (단계 3, LangGraph 체크포인터로). (b) mem0/langmem/LangGraph Store는 비목표 — 단계 4 후보.

## 아키텍처 메모

- 프론트는 KIS를 **직접 호출 안 함** — 항상 FastAPI 경유 (KIS APP_SECRET 보호). 동일하게 OpenAI 키도 백엔드에만.
- LangGraph 그래프는 `backend/app/agent/` 같은 데 모듈로. 도구는 `kis_client` 함수를 얇게 래핑 — KIS 호출 로직은 `kis_client`에 단일화.
- 인증·챗 라우터 분리(`app/routers/auth.py`, `app/routers/chat.py`), 기존 `app/routers/stocks.py` 유지.
- DB 접근은 `app/db/` (엔진, 쿼리 모음, 마이그레이션). SQL은 한 곳에 모아 둠.
- 설정은 기존 `app/config.py`에 `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET`, `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL` 추가.

## 열린 질문 (해당 단계 구현 계획에서 확정)

- 마이그레이션 도구: alembic vs 번호 붙인 `.sql` + 작은 러너. (alembic은 SQLAlchemy 생태계라 자연스럽지만 ORM 모델 없이 쓰면 약간 어색 — `--autogenerate` 없이 수기 작성) — 단계 1
- 로그인: 이메일/비밀번호만 vs OAuth(구글) 추가. (단계 1은 이메일/비밀번호로 시작 권장) — 단계 1
- 프론트 토큰 저장: httpOnly 쿠키 vs 메모리(access) + refresh 호출. (XSS/CSRF 트레이드오프) — 단계 1
- 배포 대상 구체화: 백엔드 Fly.io vs Render, Redis는 Upstash vs 매니지드, Postgres 호스트. — 단계 2 배포 시점
- LangGraph 도구 그래프의 정확한 노드/분기 구조, 스트리밍 이벤트 포맷. — 단계 2
- 챗 위젯이 컨텍스트를 어떻게 전달할지 구체화(요청 body vs URL), 종목 외 페이지에서의 기본 동작. — 단계 2

## 다음 단계

1. 사용자가 이 문서 검토 → 수정.
2. 단계 1(인증 토대)에 대해 `/superpowers:writing-plans`로 잘게 쪼갠 TDD 구현 계획 작성. (FastAPI 문법이 아직 익숙치 않다고 했으니 계획은 상세하고 교육적으로.)
3. `/superpowers:subagent-driven-development`로 단계 1 구현.
4. 단계 1 완료 후 단계 2(챗봇)에 대해 다시 1→2→3 반복. 큰 결정 있으면 `/plan-eng-review` 끼움.

## 이 세션에서 관찰한 것

- "내가 langgraph를 다뤄서 챗봇을 만들수있다라고 보여주고싶거든" — 목표가 명확하고 구체적. 막연한 "AI 서비스"가 아니라 보여줄 능력이 또렷함.
- "버전이 여러개로 있어야해? 잘몰라" — 처음이라 단계적 빌드 개념이 낯설지만, 설명하니 바로 이해함. 모르는 걸 모른다고 말하는 게 강점.
- 인증·DB 얘기에서 본인이 NestJS 경험과 `create_async_engine` 코드를 떠올림 — 백엔드 패턴 자체는 이미 알고 있고, FastAPI 문법만 새로 익히면 됨. 진입장벽이 생각보다 낮음.
