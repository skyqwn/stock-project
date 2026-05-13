# side — KIS 주식 웹앱 (기초 세팅)

한국투자증권 OpenAPI(KIS) 모의투자로 국내주식 현재가를 조회하는 스캐폴드.

- `backend/` — FastAPI (uv)
- `frontend/` — Next.js 16 (pnpm)

## 실행

### 백엔드
```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```
http://localhost:8000/api/health 로 확인.

### 프론트엔드
```powershell
cd frontend
pnpm install
pnpm dev
```
http://localhost:3000

### KIS 키 설정
`backend/.env.example` 를 `backend/.env` 로 복사하고 KIS Developers 포털
(https://apiportal.koreainvestment.com)에서 모의투자 신청 + 앱 등록 후 받은
APP_KEY / APP_SECRET 를 채운다. 키가 없어도 서버는 뜨며, 시세 조회 시 502 를 반환한다.

### 백엔드 테스트
```powershell
cd backend
uv run pytest
```
