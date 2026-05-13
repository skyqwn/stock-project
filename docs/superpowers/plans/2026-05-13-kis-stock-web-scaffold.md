# KIS 주식 웹앱 기초 세팅 스캐폴드 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국투자증권 OpenAPI(KIS) 모의투자 환경에서 국내주식 현재가를 조회해 화면에 표시하는 end-to-end 스캐폴드(Next.js 16 + FastAPI)를 만든다.

**Architecture:** 단일 레포 `side/` 아래 `backend/`(FastAPI, uv)와 `frontend/`(Next.js 16, pnpm). 프론트는 KIS를 직접 호출하지 않고 항상 FastAPI를 경유한다(APP_SECRET 보호). 백엔드는 KIS OAuth 토큰을 발급·메모리 캐싱하고 현재가 REST를 프록시한다. 백엔드는 respx로 KIS HTTP를 모킹한 TDD로 작성한다.

**Tech Stack:** FastAPI, uvicorn, httpx, pydantic-settings, pytest, respx (백엔드) / Next.js 16 App Router, TypeScript, Tailwind, pnpm (프론트) / git

> **참고:** 브레인스토밍 때 "git은 나중에 추가"로 합의했고, 이 계획의 Task 1이 바로 그 git 추가 단계다. git을 아직 안 쓰겠다면 Task 1을 건너뛰고 이후 모든 `git ...` 스텝을 무시하면 된다.

## Prerequisites

엔지니어 머신에 다음이 설치되어 있어야 한다:
- `git`
- `uv` (https://docs.astral.sh/uv/ — Python 패키지/환경 관리)
- `node` 20+ 와 `pnpm` (`npm i -g pnpm` 또는 `corepack enable pnpm`)

플랫폼은 Windows(PowerShell)를 가정한다. 셸 명령은 PowerShell 기준으로 적었다.

## File Structure

생성/수정할 파일과 책임:

```
side/
├── .gitignore                        # 생성 — Python/Node 산출물 + .env 무시
├── README.md                         # 생성 — 실행 방법
├── docs/superpowers/                  # 이미 존재 (spec, plan)
├── backend/
│   ├── pyproject.toml                # 생성(uv) — 의존성
│   ├── uv.lock                       # 생성(uv) — 잠금
│   ├── .python-version               # 생성(uv)
│   ├── .env.example                  # 생성 — KIS 키 샘플
│   ├── app/
│   │   ├── __init__.py               # 생성 — 빈 파일
│   │   ├── main.py                   # 생성 — FastAPI 앱, CORS, 라우터 등록
│   │   ├── config.py                 # 생성 — pydantic-settings 로 .env 로드
│   │   ├── kis_client.py             # 생성 — KIS 토큰 발급·캐싱 + 현재가 호출
│   │   └── routers/
│   │       ├── __init__.py           # 생성 — 빈 파일
│   │       └── stocks.py             # 생성 — /api/health, /api/stocks/{code}/price
│   └── tests/
│       ├── __init__.py               # 생성 — 빈 파일
│       ├── conftest.py               # 생성 — 토큰 캐시 초기화 픽스처
│       ├── test_health.py            # 생성 — /api/health 테스트
│       ├── test_kis_client.py        # 생성 — get_access_token / get_price 테스트
│       └── test_stocks.py            # 생성 — /api/stocks/{code}/price 라우터 테스트
└── frontend/                          # pnpm create next-app 으로 생성
    ├── .env.local.example            # 생성 — NEXT_PUBLIC_API_BASE_URL
    └── src/app/
        ├── lib/api.ts                # 생성 — FastAPI 호출 래퍼 + 타입
        └── page.tsx                  # 덮어쓰기 — 종목코드 입력 → 현재가 카드
```

---

### Task 1: 레포 초기화 + 루트 스캐폴딩

**Files:**
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: git 저장소 초기화**

작업 디렉터리(`side/`)에서:
```powershell
git init
git branch -M main
```
Expected: `Initialized empty Git repository ...`

- [ ] **Step 2: `.gitignore` 생성**

`.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/

# Node / Next.js
node_modules/
.next/
out/
.pnpm-store/

# Env
.env
.env.local
.env.*.local

# OS / Editor
.DS_Store
Thumbs.db
```

- [ ] **Step 3: `README.md` 생성 (뼈대)**

`README.md`:
```markdown
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
```

- [ ] **Step 4: 커밋**

```powershell
git add .gitignore README.md docs
git commit -m "chore: init repo with gitignore, README, design docs"
```

---

### Task 2: 백엔드 uv 프로젝트 + /api/health 엔드포인트 (TDD)

**Files:**
- Create: `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version` (uv가 생성)
- Create: `backend/app/__init__.py`, `backend/app/main.py`
- Create: `backend/app/routers/__init__.py`, `backend/app/routers/stocks.py`
- Create: `backend/tests/__init__.py`, `backend/tests/test_health.py`

- [ ] **Step 1: uv 프로젝트 생성**

```powershell
cd backend
uv init --name kis-backend --python 3.12
```
그 다음 uv가 생성한 샘플 파일을 삭제한다 (있는 것만):
```powershell
Remove-Item main.py -ErrorAction SilentlyContinue
Remove-Item hello.py -ErrorAction SilentlyContinue
Remove-Item README.md -ErrorAction SilentlyContinue
```
Expected: `backend/pyproject.toml`, `backend/.python-version` 존재.

- [ ] **Step 2: 의존성 추가**

```powershell
uv add fastapi "uvicorn[standard]" httpx pydantic-settings
uv add --dev pytest respx
```
Expected: `pyproject.toml` 의 `[project].dependencies` 와 `[dependency-groups].dev` 채워짐, `uv.lock` 생성.

- [ ] **Step 3: 패키지 디렉터리 + `__init__.py` 생성**

빈 파일 3개 생성: `backend/app/__init__.py`, `backend/app/routers/__init__.py`, `backend/tests/__init__.py` (내용 없음).

- [ ] **Step 4: 실패하는 테스트 작성**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 5: 테스트 실패 확인**

```powershell
uv run pytest tests/test_health.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (또는 `app`).

- [ ] **Step 6: 최소 구현 — 라우터 + 앱**

`backend/app/routers/stocks.py`:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stocks

app = FastAPI(title="KIS Stock Scaffold")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
```

- [ ] **Step 7: 테스트 통과 확인**

```powershell
uv run pytest tests/test_health.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 8: 서버 수동 확인 (선택)**

```powershell
uv run uvicorn app.main:app --port 8000
```
브라우저에서 http://localhost:8000/api/health → `{"status":"ok"}`. 확인 후 Ctrl+C.

- [ ] **Step 9: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): uv project scaffold with /api/health"
```

---

### Task 3: 설정 모듈 (config.py) + .env.example

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_config.py`:
```python
from app.config import Settings


def test_default_base_url_is_paper_trading():
    s = Settings(_env_file=None)
    assert s.kis_base_url == "https://openapivts.koreainvestment.com:29443"
    assert s.kis_app_key == ""
    assert s.kis_app_secret == ""
    assert s.kis_account == ""
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
cd backend
uv run pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: config.py 구현**

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    kis_app_key: str = ""
    kis_app_secret: str = ""
    # 모의투자 도메인. 실거래는 https://openapi.koreainvestment.com:9443
    kis_base_url: str = "https://openapivts.koreainvestment.com:29443"
    kis_account: str = ""  # 모의투자 계좌번호 (현재가 조회엔 불필요, 추후 확장용)


settings = Settings()
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
uv run pytest tests/test_config.py -v
```
Expected: PASS.

- [ ] **Step 5: `.env.example` 생성**

`backend/.env.example`:
```
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_ACCOUNT=
```

- [ ] **Step 6: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): settings module + .env.example"
```

---

### Task 4: KIS 클라이언트 — 토큰 발급 + 캐싱 (TDD)

**Files:**
- Create: `backend/app/kis_client.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_kis_client.py`

- [ ] **Step 1: 토큰 캐시 초기화 픽스처 작성**

`backend/tests/conftest.py`:
```python
import pytest


@pytest.fixture(autouse=True)
def _reset_kis_token_cache():
    # 각 테스트 전후로 모듈 수준 토큰 캐시를 비운다.
    from app import kis_client

    kis_client.clear_token_cache()
    yield
    kis_client.clear_token_cache()
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_kis_client.py`:
```python
import httpx
import pytest
import respx

from app import kis_client
from app.config import settings

BASE = "https://openapivts.koreainvestment.com:29443"
TOKEN_URL = f"{BASE}/oauth2/tokenP"


@pytest.fixture(autouse=True)
def _kis_creds(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "test-key")
    monkeypatch.setattr(settings, "kis_app_secret", "test-secret")
    monkeypatch.setattr(settings, "kis_base_url", BASE)


@respx.mock
@pytest.mark.anyio
async def test_get_access_token_fetches_and_caches():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "abc123", "token_type": "Bearer", "expires_in": 86400}
        )
    )
    token1 = await kis_client.get_access_token()
    token2 = await kis_client.get_access_token()
    assert token1 == "abc123"
    assert token2 == "abc123"
    assert route.call_count == 1  # 두 번째 호출은 캐시 사용


@respx.mock
@pytest.mark.anyio
async def test_get_access_token_raises_when_creds_missing(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "")
    with pytest.raises(kis_client.KisError):
        await kis_client.get_access_token()
```

> 비고: 이 테스트는 async 이므로 anyio 플러그인이 필요하다. Step 3에서 `pyproject.toml` 에 pytest 설정을 추가한다.

- [ ] **Step 3: pytest async 설정 + anyio 추가**

```powershell
cd backend
uv add --dev anyio
```
그리고 `backend/pyproject.toml` 끝에 추가:
```toml
[tool.pytest.ini_options]
anyio_mode = "auto"
```
(`anyio_mode = "auto"` 로 `@pytest.mark.anyio` 가 붙은 async 테스트가 자동 실행된다. `asyncio` 백엔드만 쓰므로 별도 설정 불필요.)

- [ ] **Step 4: 테스트 실패 확인**

```powershell
uv run pytest tests/test_kis_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.kis_client'`.

- [ ] **Step 5: kis_client.py 구현 (토큰 부분)**

`backend/app/kis_client.py`:
```python
import time

import httpx

from app.config import settings


class KisError(RuntimeError):
    """KIS API 가 오류 응답을 반환했을 때."""


# (access_token, 만료 epoch초) — 모듈 수준 캐시. 테스트는 clear_token_cache() 로 초기화.
_cached_token: tuple[str, float] | None = None


def clear_token_cache() -> None:
    global _cached_token
    _cached_token = None


async def get_access_token() -> str:
    global _cached_token
    now = time.time()
    if _cached_token is not None and _cached_token[1] - 60 > now:
        return _cached_token[0]

    if not settings.kis_app_key or not settings.kis_app_secret:
        raise KisError("KIS_APP_KEY / KIS_APP_SECRET 환경변수가 설정되지 않았습니다.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.kis_base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": settings.kis_app_key,
                "appsecret": settings.kis_app_secret,
            },
        )
    if resp.status_code != 200:
        raise KisError(f"토큰 발급 실패: HTTP {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise KisError(f"토큰 응답에 access_token 없음: {data}")
    expires_in = float(data.get("expires_in", 0) or 0)
    _cached_token = (token, now + expires_in)
    return token
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
uv run pytest tests/test_kis_client.py -v
```
Expected: PASS (2 passed).

- [ ] **Step 7: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): KIS OAuth token issuance with in-memory cache"
```

---

### Task 5: KIS 클라이언트 — 현재가 조회 (TDD)

**Files:**
- Modify: `backend/app/kis_client.py` (함수 추가)
- Modify: `backend/tests/test_kis_client.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`backend/tests/test_kis_client.py` 끝에 추가:
```python
PRICE_URL = f"{BASE}/uapi/domestic-stock/v1/quoting/inquire-price"


def _mock_token():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "abc123", "token_type": "Bearer", "expires_in": 86400}
        )
    )


@respx.mock
@pytest.mark.anyio
async def test_get_price_parses_output():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "정상처리 되었습니다.",
                "output": {
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "70000",
                    "prdy_vrss": "1000",
                    "prdy_ctrt": "1.45",
                    "acml_vol": "12345678",
                },
            },
        )
    )
    result = await kis_client.get_price("005930")
    assert result == {
        "code": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_rate": 1.45,
        "volume": 12345678,
    }


@respx.mock
@pytest.mark.anyio
async def test_get_price_raises_on_error_rt_cd():
    _mock_token()
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(200, json={"rt_cd": "1", "msg1": "조회할 자료가 없습니다."})
    )
    with pytest.raises(kis_client.KisError):
        await kis_client.get_price("000000")
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
cd backend
uv run pytest tests/test_kis_client.py -v
```
Expected: FAIL — `AttributeError: module 'app.kis_client' has no attribute 'get_price'`.

- [ ] **Step 3: get_price 구현 — `kis_client.py` 끝에 추가**

```python
async def get_price(code: str) -> dict:
    token = await get_access_token()
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": settings.kis_app_key,
        "appsecret": settings.kis_app_secret,
        "tr_id": "FHKST01010100",
        "custtype": "P",
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.kis_base_url}/uapi/domestic-stock/v1/quoting/inquire-price",
            headers=headers,
            params=params,
        )
    if resp.status_code != 200:
        raise KisError(f"현재가 조회 실패: HTTP {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("rt_cd") != "0":
        raise KisError(f"현재가 조회 오류: {data.get('msg1', data)}")
    output = data.get("output") or {}
    return {
        "code": code,
        "name": output.get("hts_kor_isnm", ""),
        "price": int(output.get("stck_prpr", 0) or 0),
        "change": int(output.get("prdy_vrss", 0) or 0),
        "change_rate": float(output.get("prdy_ctrt", 0) or 0),
        "volume": int(output.get("acml_vol", 0) or 0),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
uv run pytest tests/test_kis_client.py -v
```
Expected: PASS (4 passed).

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): KIS current price lookup"
```

---

### Task 6: 현재가 라우터 + main 연결 (TDD)

**Files:**
- Modify: `backend/app/routers/stocks.py` (엔드포인트 추가)
- Create: `backend/tests/test_stocks.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_stocks.py`:
```python
import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

BASE = "https://openapivts.koreainvestment.com:29443"
TOKEN_URL = f"{BASE}/oauth2/tokenP"
PRICE_URL = f"{BASE}/uapi/domestic-stock/v1/quoting/inquire-price"


@pytest.fixture(autouse=True)
def _kis_creds(monkeypatch):
    monkeypatch.setattr(settings, "kis_app_key", "test-key")
    monkeypatch.setattr(settings, "kis_app_secret", "test-secret")
    monkeypatch.setattr(settings, "kis_base_url", BASE)


@respx.mock
def test_stock_price_endpoint_ok():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 86400})
    )
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "OK",
                "output": {
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "70000",
                    "prdy_vrss": "1000",
                    "prdy_ctrt": "1.45",
                    "acml_vol": "12345678",
                },
            },
        )
    )
    client = TestClient(app)
    resp = client.get("/api/stocks/005930/price")
    assert resp.status_code == 200
    assert resp.json() == {
        "code": "005930",
        "name": "삼성전자",
        "price": 70000,
        "change": 1000,
        "change_rate": 1.45,
        "volume": 12345678,
    }


@respx.mock
def test_stock_price_endpoint_returns_502_on_kis_error():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 86400})
    )
    respx.get(PRICE_URL).mock(
        return_value=httpx.Response(200, json={"rt_cd": "1", "msg1": "조회할 자료가 없습니다."})
    )
    client = TestClient(app)
    resp = client.get("/api/stocks/000000/price")
    assert resp.status_code == 502
    assert "조회" in resp.json()["detail"]
```

> 비고: 이 테스트들은 `tests/conftest.py` 의 autouse 픽스처가 매 테스트마다 토큰 캐시를 비워주므로 순서에 무관하게 동작한다.

- [ ] **Step 2: 테스트 실패 확인**

```powershell
cd backend
uv run pytest tests/test_stocks.py -v
```
Expected: FAIL — `/api/stocks/005930/price` 가 404 (라우트 없음).

- [ ] **Step 3: 라우터에 엔드포인트 추가 — `app/routers/stocks.py` 전체를 아래로 교체**

```python
from fastapi import APIRouter, HTTPException

from app import kis_client

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stocks/{code}/price")
async def stock_price(code: str) -> dict:
    try:
        return await kis_client.get_price(code)
    except kis_client.KisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

(main.py 는 이미 `stocks.router` 를 include 하므로 수정 불필요.)

- [ ] **Step 4: 전체 테스트 통과 확인**

```powershell
uv run pytest -v
```
Expected: PASS — test_health(1) + test_config(1) + test_kis_client(4) + test_stocks(2) = 8 passed.

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): /api/stocks/{code}/price endpoint"
```

---

### Task 7: 프론트엔드 생성 + API 래퍼

**Files:**
- Create: `frontend/` (pnpm create next-app 산출물 전체)
- Create: `frontend/src/app/lib/api.ts`
- Create: `frontend/.env.local.example`

- [ ] **Step 1: Next.js 16 앱 생성**

작업 디렉터리(`side/`)에서:
```powershell
pnpm create next-app frontend --ts --tailwind --eslint --app --src-dir --use-pnpm --import-alias "@/*" --no-turbopack
```
프롬프트가 뜨면 위 플래그에 맞춰 답한다 (TypeScript: Yes, Tailwind: Yes, ESLint: Yes, App Router: Yes, `src/` 디렉터리: Yes, import alias `@/*`: Yes). 생성 후 확인:
```powershell
Test-Path frontend/src/app/page.tsx
```
Expected: `True`. (Next.js 메이저 버전은 16.x 여야 한다 — `frontend/package.json` 의 `next` 버전 확인.)

- [ ] **Step 2: `.env.local.example` 생성**

`frontend/.env.local.example`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

또한 로컬 개발용으로 복사:
```powershell
Copy-Item frontend/.env.local.example frontend/.env.local
```

- [ ] **Step 3: API 래퍼 작성**

`frontend/src/app/lib/api.ts`:
```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface StockPrice {
  code: string;
  name: string;
  price: number;
  change: number;
  change_rate: number;
  volume: number;
}

export async function fetchPrice(code: string): Promise<StockPrice> {
  const res = await fetch(`${API_BASE}/api/stocks/${code}/price`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `요청 실패 (${res.status})`);
  }
  return (await res.json()) as StockPrice;
}
```

- [ ] **Step 4: 빌드/린트로 검증**

```powershell
cd frontend
pnpm install
pnpm lint
pnpm build
```
Expected: lint 통과, build 성공 (에러 없음).

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add frontend
git commit -m "feat(frontend): next.js 16 scaffold + API client wrapper"
```

---

### Task 8: 프론트엔드 페이지 — 종목 현재가 조회 UI

**Files:**
- Modify (덮어쓰기): `frontend/src/app/page.tsx`

- [ ] **Step 1: `page.tsx` 전체를 아래로 교체**

`frontend/src/app/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import { fetchPrice, type StockPrice } from "@/app/lib/api";

export default function Home() {
  const [code, setCode] = useState("005930");
  const [data, setData] = useState<StockPrice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await fetchPrice(code.trim());
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="mb-6 text-2xl font-bold">국내주식 현재가 조회 (모의투자)</h1>
      <form onSubmit={onSubmit} className="mb-6 flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="종목코드 (예: 005930)"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "조회 중..." : "조회"}
        </button>
      </form>

      {error && <p className="text-red-600">{error}</p>}

      {data && (
        <div className="rounded-lg border p-4">
          <p className="text-lg font-semibold">
            {data.name} ({data.code})
          </p>
          <p className="text-3xl font-bold">{data.price.toLocaleString()}원</p>
          <p className={data.change >= 0 ? "text-red-600" : "text-blue-600"}>
            {data.change >= 0 ? "▲" : "▼"} {Math.abs(data.change).toLocaleString()} (
            {data.change_rate}%)
          </p>
          <p className="text-sm text-gray-500">
            누적 거래량 {data.volume.toLocaleString()}
          </p>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: 린트/빌드 검증**

```powershell
cd frontend
pnpm lint
pnpm build
```
Expected: lint 통과, build 성공.

- [ ] **Step 3: 커밋**

```powershell
cd ..
git add frontend
git commit -m "feat(frontend): stock price lookup page"
```

---

### Task 9: 수동 end-to-end 확인 + 마무리

**Files:** (변경 없음 — 검증 단계)

- [ ] **Step 1: 백엔드 기동**

새 터미널에서:
```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: 프론트엔드 기동**

또 다른 터미널에서:
```powershell
cd frontend
pnpm dev
```

- [ ] **Step 3: 브라우저 확인**

http://localhost:3000 접속 → 종목코드 `005930` 으로 "조회" 클릭.
- `backend/.env` 에 유효한 KIS 모의투자 키가 있으면 → 현재가 카드 표시.
- 키가 없으면 → 빨간 에러 메시지(502 detail: "KIS_APP_KEY / KIS_APP_SECRET 환경변수가 설정되지 않았습니다.") 표시. **이것도 정상** — end-to-end 경로(프론트→FastAPI→에러처리→프론트 표시)가 동작함을 의미.

http://localhost:8000/api/health → `{"status":"ok"}` 확인.

- [ ] **Step 4: 전체 백엔드 테스트 재실행**

```powershell
cd backend
uv run pytest -v
```
Expected: 8 passed.

- [ ] **Step 5: 최종 커밋 (변경 있으면)**

README 등에 보완할 게 있으면 수정 후:
```powershell
cd ..
git add -A
git commit -m "docs: finalize scaffold readme"
```
변경이 없으면 이 스텝은 생략.

---

## Self-Review

**1. Spec coverage:**
- 폴더 구조 (단일 레포 backend/ + frontend/) → Task 1, 2, 7 ✓
- backend: config.py (pydantic-settings) → Task 3 ✓
- backend: kis_client.py (토큰 발급·캐싱, get_price, httpx) → Task 4, 5 ✓
- backend: routers/stocks.py (/api/health, /api/stocks/{code}/price, 502) → Task 2, 6 ✓
- backend: main.py (CORS localhost:3000, 라우터 등록) → Task 2 ✓
- backend: respx 모킹 테스트 (health 200, price 형식, 오류 502) → Task 2, 6 ✓ (추가로 kis_client 단위 테스트 Task 4,5)
- backend/.env.example → Task 3 ✓
- frontend: pnpm create next-app (App Router/TS/Tailwind/ESLint) → Task 7 ✓
- frontend: lib/api.ts (fetchPrice) → Task 7 ✓
- frontend: page.tsx (종목코드 입력 기본값 005930, 카드, 로딩/에러) → Task 8 ✓
- frontend/.env.local.example (NEXT_PUBLIC_API_BASE_URL) → Task 7 ✓
- 실행 방법 README → Task 1 (작성), Task 9 (보완) ✓
- 보안 메모 (프론트가 KIS 직접 호출 안 함) → 설계상 반영(프론트는 FastAPI만 호출) ✓
- 비목표(로그인/DB/잔고/주문/WebSocket/차트/docker/git-나중) → 계획에 미포함, git은 명시적으로 Task 1에서 추가하며 안내 ✓
- 빠진 것: 없음.

**2. Placeholder scan:** "TBD"/"TODO"/"적절히 처리" 류 없음. 모든 코드 스텝에 실제 코드 포함. ✓

**3. Type consistency:**
- `StockPrice` 인터페이스 키 (`code, name, price, change, change_rate, volume`) — api.ts(Task 7), page.tsx(Task 8), 백엔드 `get_price` 반환(Task 5), 라우터 테스트(Task 6) 모두 일치. ✓
- `kis_client.KisError`, `kis_client.get_access_token`, `kis_client.get_price`, `kis_client.clear_token_cache` — Task 4/5 정의, Task 6 라우터·conftest·테스트에서 동일 이름 사용. ✓
- 토큰 캐시 변수 `_cached_token` — Task 4에서 정의, `clear_token_cache()` 에서 동일 이름 참조. ✓
- FastAPI app 객체 `app` — Task 2 `app/main.py` 정의, 테스트에서 `from app.main import app`. ✓
- 라우터 prefix `/api` + 경로 `/health`, `/stocks/{code}/price` → 최종 URL `/api/health`, `/api/stocks/{code}/price` — 테스트 URL과 일치. ✓

이슈 없음.

---

## Execution Handoff

이 계획은 `docs/superpowers/plans/2026-05-13-kis-stock-web-scaffold.md` 에 저장됨.
