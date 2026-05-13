# side — KIS 주식 웹앱

한국투자증권 OpenAPI(KIS) **모의투자**로 국내주식 정보를 다루는 웹앱.

## 구조
- `backend/` — FastAPI (uv). KIS OAuth 토큰 발급·캐싱 + REST 프록시. `app/main.py`, `app/config.py`, `app/kis_client.py`, `app/routers/stocks.py`. 테스트는 `pytest` + `respx`(KIS HTTP 모킹).
- `frontend/` — Next.js 16 (pnpm, App Router, TypeScript, Tailwind v4). 프론트는 KIS를 직접 호출하지 않고 항상 FastAPI 경유 (APP_SECRET 보호).
- `docs/superpowers/specs/`, `docs/superpowers/plans/` — 기능별 설계 문서·구현 계획. gstack/superpowers 스킬이 자동으로 참조.

## 실행
- 백엔드: `cd backend; uv sync; uv run uvicorn app.main:app --reload --port 8000` (헬스: `/api/health`)
- 프론트: `cd frontend; pnpm install; pnpm dev` → http://localhost:3000
- 백엔드 테스트: `cd backend; uv run pytest`
- KIS 키: `backend/.env.example` → `backend/.env` 복사 후 [KIS Developers](https://apiportal.koreainvestment.com)에서 모의투자 신청·앱 등록 후 채움. 키 없어도 서버는 기동, 시세 조회 시 502 안내.

## 개발 규칙
- 새 기능 흐름: 설계(brainstorming/office-hours) → `docs/superpowers/plans/`에 계획 → 구현(subagent-driven-development, TDD). 큰 기능·구조 변경은 `/autoplan`이나 `/plan-eng-review`로 계획 리뷰.
- 자잘한 수정(오타, 스타일, 한 줄 버그)은 TDD·계획 절차 생략하고 바로 고쳐도 됨.
- 커밋 단위는 작게, 자주.
- KIS 호출은 `backend/app/kis_client.py`에만. 새 KIS 엔드포인트 추가 시 `tr_id`와 응답 필드 매핑을 그 파일에 둠.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
