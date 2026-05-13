# 인증 토대 (단계 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자 회원가입/로그인/토큰 갱신/로그아웃 + 보호된 `/api/auth/me` 가 동작하는 인증 토대를 완성한다 (백엔드 FastAPI + Postgres + Redis + 프론트 Next.js 16 페이지/컨텍스트까지).

**Architecture:** 백엔드는 SQLAlchemy Core async 엔진으로 Postgres에 연결하고 raw SQL(`text()`)로 users 테이블을 다룬다. access JWT(짧은 TTL)는 `Authorization: Bearer` 헤더로, refresh token(UUID)은 Redis에 `user_id`와 함께 TTL로 보관·로테이션한다. 비밀번호는 argon2로 해싱한다. 프론트는 localStorage에 두 토큰을 저장하고 401 응답 시 refresh를 자동 호출한다.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x Core(async, asyncpg) / Postgres 16 / redis-py(async) / python-jose[cryptography] / argon2-cffi / pytest + respx + fakeredis / Next.js 16 / TypeScript / Tailwind v4

> **참고 — 설계 문서:** `docs/superpowers/specs/2026-05-13-stock-chatbot-design.md` 의 "단계 1" 섹션. 이 계획이 그것의 구현 형태.
>
> **참고 — 인간 독자에게:** 16개 작업이지만 각 작업이 작아요. 한 번에 다 하지 말고 한 작업씩 하세요. 막히면 그 작업만 보고 질문하세요. `subagent-driven-development`로 돌리면 작업마다 서브에이전트 + 리뷰가 자동으로 돌아갑니다.

---

## File Structure

생성 / 수정할 파일과 책임:

```
side/
├── docker-compose.yml                   # 신규 — postgres + redis 로컬 인프라
├── docker/
│   └── postgres-init.sql                # 신규 — side_test DB 생성
├── backend/
│   ├── pyproject.toml                   # 수정 — deps 추가
│   ├── .env.example                     # 수정 — DATABASE_URL/REDIS_URL/JWT_* 추가
│   ├── app/
│   │   ├── config.py                    # 수정 — 신규 settings 추가
│   │   ├── main.py                      # 수정 — lifespan(DB migrate, Redis init), CORS POST 허용, auth router include
│   │   ├── redis_client.py              # 신규 — Redis async client + refresh-token 헬퍼
│   │   ├── db/
│   │   │   ├── __init__.py              # 신규 — 빈 파일
│   │   │   ├── engine.py                # 신규 — create_async_engine + get_conn dep
│   │   │   ├── migrate.py               # 신규 — .sql 파일 순차 적용 러너
│   │   │   ├── migrations/
│   │   │   │   └── 0001_users.sql       # 신규 — users 테이블
│   │   │   └── queries/
│   │   │       ├── __init__.py          # 신규 — 빈 파일
│   │   │       └── users.py             # 신규 — users CRUD (text() SQL)
│   │   ├── auth/
│   │   │   ├── __init__.py              # 신규 — 빈 파일
│   │   │   ├── passwords.py             # 신규 — argon2 해싱
│   │   │   ├── tokens.py                # 신규 — JWT 인코드/디코드, refresh id 생성
│   │   │   ├── service.py               # 신규 — register/login/refresh/logout 비즈니스 로직 + 커스텀 예외
│   │   │   └── dependencies.py          # 신규 — get_current_user FastAPI dep
│   │   ├── schemas/
│   │   │   ├── __init__.py              # 신규 — 빈 파일
│   │   │   └── auth.py                  # 신규 — pydantic 요청/응답 모델
│   │   └── routers/
│   │       └── auth.py                  # 신규 — /api/auth/{register,login,refresh,logout,me}
│   └── tests/
│       ├── conftest.py                  # 수정 — 테스트 DB 셋업, fakeredis 픽스처
│       ├── test_passwords.py            # 신규
│       ├── test_tokens.py               # 신규
│       ├── test_users_queries.py        # 신규
│       ├── test_redis_client.py         # 신규
│       ├── test_auth_register.py        # 신규
│       ├── test_auth_login.py           # 신규
│       ├── test_auth_refresh.py         # 신규
│       ├── test_auth_logout.py          # 신규
│       └── test_auth_me.py              # 신규
└── frontend/
    └── src/app/
        ├── lib/
        │   ├── api.ts                   # 수정 — Authorization 자동 첨부, 401 시 refresh 재시도
        │   └── auth.tsx                 # 신규 — AuthContext, 토큰 저장, login/register/refresh/logout
        ├── layout.tsx                   # 수정 — AuthProvider 래핑
        ├── page.tsx                     # 수정 — 로그인 상태 표시 + /me 호출
        └── (auth)/
            ├── login/page.tsx           # 신규
            └── register/page.tsx        # 신규
```

## Prerequisites
- Docker Desktop 실행 가능해야 함 (Postgres + Redis 로컬용).
- 백엔드: `uv` 이미 설치. 프론트: `pnpm` 이미 설치.

---

### Task 1: 인프라 셋업 — docker-compose + 백엔드 의존성 + 환경변수

**Files:**
- Create: `docker-compose.yml`, `docker/postgres-init.sql`
- Modify: `backend/pyproject.toml` (deps 추가), `backend/.env.example`

- [ ] **Step 1: `docker-compose.yml` 생성**

루트(`side/`)에 `docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: side
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 2: `docker/postgres-init.sql` 생성**

`docker/postgres-init.sql`:
```sql
CREATE DATABASE side_test;
```

(POSTGRES_DB가 자동으로 `side` DB를 만들어주므로 여기선 테스트 DB만 추가.)

- [ ] **Step 3: docker compose 기동 + 헬스 확인**

```powershell
docker compose up -d
docker compose ps
```
Expected: `postgres`, `redis` 모두 `healthy`.

- [ ] **Step 4: 백엔드 의존성 추가**

```powershell
cd backend
uv add "sqlalchemy[asyncio]" asyncpg redis "python-jose[cryptography]" argon2-cffi "pydantic[email]"
uv add --dev fakeredis
```

확인: `pyproject.toml`의 `[project].dependencies`에 `sqlalchemy`, `asyncpg`, `redis`, `python-jose`, `argon2-cffi`, `pydantic[email]` 가 있고, `[dependency-groups].dev`에 `fakeredis`가 추가됨.

- [ ] **Step 5: `backend/.env.example` 업데이트**

기존 KIS 변수 아래에 추가:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/side
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-this-in-prod-use-openssl-rand-hex-32
JWT_ACCESS_TTL_SECONDS=900
JWT_REFRESH_TTL_SECONDS=604800
```

또한 `backend/.env`를 생성(개발용 — git에 안 잡힘, 위와 동일한 내용으로):
```powershell
Copy-Item .env.example .env
```

- [ ] **Step 6: 커밋**

루트로 이동 후:
```powershell
cd ..
git add docker-compose.yml docker/postgres-init.sql backend/pyproject.toml backend/uv.lock backend/.env.example
git commit -m "chore(infra): docker-compose for postgres/redis, backend auth deps"
```

---

### Task 2: 설정 — `app/config.py`에 새 설정 추가

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/tests/test_config_auth.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_config_auth.py`:
```python
from app.config import Settings


def test_auth_settings_defaults():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.redis_url.startswith("redis://")
    assert s.jwt_secret != ""  # 어떤 값이든 빈 문자열이 아니어야 — env로 강제될 것
    assert s.jwt_access_ttl_seconds == 900
    assert s.jwt_refresh_ttl_seconds == 604800
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
cd backend
uv run pytest tests/test_config_auth.py -v
```
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'database_url'` 등.

- [ ] **Step 3: `app/config.py` 수정**

기존 클래스에 필드 추가:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # KIS
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_base_url: str = "https://openapivts.koreainvestment.com:29443"
    kis_account: str = ""

    # DB / Redis
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/side"
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "dev-only-secret-change-in-prod"
    jwt_access_ttl_seconds: int = 900     # 15분
    jwt_refresh_ttl_seconds: int = 604800  # 7일


settings = Settings()
```

> 메모: `jwt_secret`는 디폴트에 "dev only"라고 적어둠 — 실제 배포 때 반드시 환경변수로 덮어쓸 것. 운영에서 디폴트 그대로면 보안 사고.

- [ ] **Step 4: 테스트 통과 확인**

```powershell
uv run pytest tests/test_config_auth.py -v
```
Expected: PASS.

- [ ] **Step 5: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): auth/DB/Redis settings in config"
```

---

### Task 3: DB 엔진 + 마이그레이션 러너 + 첫 마이그레이션(users)

**Files:**
- Create: `backend/app/db/__init__.py` (빈), `backend/app/db/engine.py`, `backend/app/db/migrate.py`, `backend/app/db/migrations/0001_users.sql`
- Create: `backend/tests/test_migrate.py`

- [ ] **Step 1: 빈 파일 생성**

`backend/app/db/__init__.py` (내용 없음). 마이그레이션 디렉터리도:
```powershell
New-Item -ItemType Directory -Force backend/app/db/migrations | Out-Null
```

- [ ] **Step 2: 마이그레이션 SQL 작성**

`backend/app/db/migrations/0001_users.sql`:
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 3: DB 엔진 작성**

`backend/app/db/engine.py`:
```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.config import settings


# 모듈 수준 엔진 — 앱 전역에서 공유. lifespan에서 dispose됨.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=0,
    pool_recycle=300,
)


async def get_conn() -> AsyncGenerator[AsyncConnection, None]:
    """FastAPI Depends — 요청당 트랜잭션. 정상 종료 시 자동 commit, 예외 시 rollback."""
    async with engine.begin() as conn:
        yield conn
```

> 메모: `engine.begin()`은 트랜잭션 컨텍스트 — `await conn.commit()` 안 불러도 됨. `engine.connect()`는 commit을 직접 해야 함.

- [ ] **Step 4: 마이그레이션 러너 작성**

`backend/app/db/migrate.py`:
```python
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def apply_migrations(engine: AsyncEngine) -> list[str]:
    """순서대로 .sql 파일을 적용. 이미 적용된 건 건너뜀. 새로 적용한 버전 목록 반환."""
    applied_now: list[str] = []
    async with engine.begin() as conn:
        # 마이그레이션 추적 테이블
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        already_applied = {row[0] for row in result.all()}

        for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            version = sql_file.stem  # "0001_users"
            if version in already_applied:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            # exec_driver_sql로 멀티 스테이트먼트 안전 실행
            await conn.exec_driver_sql(sql)
            await conn.execute(
                text("INSERT INTO schema_migrations(version) VALUES (:v)"),
                {"v": version},
            )
            applied_now.append(version)
    return applied_now
```

- [ ] **Step 5: 실패하는 테스트 작성**

`backend/tests/test_migrate.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.migrate import apply_migrations


TEST_URL = settings.database_url.replace("/side", "/side_test")


@pytest.fixture
async def test_engine():
    eng = create_async_engine(TEST_URL)
    # 깨끗하게 시작
    async with eng.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS schema_migrations CASCADE"))
    yield eng
    await eng.dispose()


@pytest.mark.anyio
async def test_apply_migrations_creates_users_table(test_engine):
    applied = await apply_migrations(test_engine)
    assert "0001_users" in applied
    async with test_engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' ORDER BY ordinal_position"
        ))
        cols = [row[0] for row in result.all()]
    assert cols == ["id", "email", "password_hash", "created_at", "updated_at"]


@pytest.mark.anyio
async def test_apply_migrations_is_idempotent(test_engine):
    await apply_migrations(test_engine)
    applied_again = await apply_migrations(test_engine)
    assert applied_again == []  # 두 번째 호출은 적용할 게 없어야 함
```

- [ ] **Step 6: 테스트 실패 확인**

먼저 `docker compose up -d`로 Postgres 떠 있는지 확인.
```powershell
cd backend
uv run pytest tests/test_migrate.py -v
```
Expected: 처음엔 PASS할 수도 있고 import fail할 수도 있음. 만약 PASS면 좋고, fail이면 메시지 보고 위 코드 점검.

- [ ] **Step 7: 테스트 통과 확인 & 커밋**

```powershell
uv run pytest tests/test_migrate.py -v
```
Expected: 2 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): db engine, migration runner, users migration"
```

---

### Task 4: User 쿼리 모듈 (raw SQL) + 테스트 인프라 정비

**Files:**
- Create: `backend/app/db/queries/__init__.py` (빈), `backend/app/db/queries/users.py`
- Modify: `backend/tests/conftest.py` (테스트 DB 픽스처 추가)
- Create: `backend/tests/test_users_queries.py`

- [ ] **Step 1: 빈 `__init__.py`**

`backend/app/db/queries/__init__.py` (내용 없음).

- [ ] **Step 2: 테스트 인프라 확장 — `conftest.py` 수정**

`backend/tests/conftest.py` (기존 `_reset_kis_token_cache` 유지하고 아래 픽스처들 **추가**):
```python
import os

# 테스트용 DB/Redis 환경변수 — app 임포트 전에 세팅
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/side_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")  # fakeredis로 덮음
os.environ.setdefault("JWT_SECRET", "test-only-secret")
os.environ.setdefault("JWT_ACCESS_TTL_SECONDS", "900")
os.environ.setdefault("JWT_REFRESH_TTL_SECONDS", "604800")

import pytest


@pytest.fixture(autouse=True)
def _reset_kis_token_cache():
    from app import kis_client

    kis_client.clear_token_cache()
    yield
    kis_client.clear_token_cache()


@pytest.fixture(scope="session")
async def _migrated_test_db():
    """세션 전체에 1회 — 테스트 DB에 마이그레이션 적용."""
    from app.db.engine import engine
    from app.db.migrate import apply_migrations

    await apply_migrations(engine)
    yield


@pytest.fixture(autouse=True)
async def _clean_db(_migrated_test_db):
    """매 테스트 전 users 테이블을 비움. schema_migrations는 유지."""
    from sqlalchemy import text
    from app.db.engine import engine

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
    yield
```

> 메모: `os.environ.setdefault`는 app 임포트보다 먼저 와야 `Settings()`가 그 값을 읽음. `setdefault`라 이미 설정된 환경변수는 덮어쓰지 않음.

- [ ] **Step 3: 실패하는 테스트 작성**

`backend/tests/test_users_queries.py`:
```python
import pytest

from app.db.engine import engine
from app.db.queries import users as users_q


@pytest.mark.anyio
async def test_create_and_get_user_by_email():
    async with engine.begin() as conn:
        user = await users_q.create_user(conn, "alice@example.com", "hashed-pw")
    assert user.id > 0
    assert user.email == "alice@example.com"
    assert user.password_hash == "hashed-pw"

    async with engine.begin() as conn:
        got = await users_q.get_user_by_email(conn, "alice@example.com")
    assert got is not None
    assert got.id == user.id


@pytest.mark.anyio
async def test_get_user_by_email_returns_none_for_missing():
    async with engine.begin() as conn:
        got = await users_q.get_user_by_email(conn, "missing@example.com")
    assert got is None


@pytest.mark.anyio
async def test_get_user_by_id():
    async with engine.begin() as conn:
        u = await users_q.create_user(conn, "bob@example.com", "h")
        got = await users_q.get_user_by_id(conn, u.id)
    assert got is not None
    assert got.email == "bob@example.com"


@pytest.mark.anyio
async def test_create_user_unique_email_raises():
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        await users_q.create_user(conn, "dup@example.com", "h1")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await users_q.create_user(conn, "dup@example.com", "h2")
```

- [ ] **Step 4: 테스트 실패 확인**

```powershell
cd backend
uv run pytest tests/test_users_queries.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.queries.users'`.

- [ ] **Step 5: `users.py` 구현**

`backend/app/db/queries/users.py`:
```python
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class User:
    id: int
    email: str
    password_hash: str


async def create_user(conn: AsyncConnection, email: str, password_hash: str) -> User:
    result = await conn.execute(
        text(
            "INSERT INTO users(email, password_hash) "
            "VALUES (:email, :hash) "
            "RETURNING id, email, password_hash"
        ),
        {"email": email, "hash": password_hash},
    )
    row = result.one()
    return User(id=row.id, email=row.email, password_hash=row.password_hash)


async def get_user_by_email(conn: AsyncConnection, email: str) -> User | None:
    result = await conn.execute(
        text("SELECT id, email, password_hash FROM users WHERE email = :email"),
        {"email": email},
    )
    row = result.one_or_none()
    return User(id=row.id, email=row.email, password_hash=row.password_hash) if row else None


async def get_user_by_id(conn: AsyncConnection, user_id: int) -> User | None:
    result = await conn.execute(
        text("SELECT id, email, password_hash FROM users WHERE id = :id"),
        {"id": user_id},
    )
    row = result.one_or_none()
    return User(id=row.id, email=row.email, password_hash=row.password_hash) if row else None
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
uv run pytest tests/test_users_queries.py -v
```
Expected: 4 passed.

- [ ] **Step 7: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): users queries with raw SQL + test DB fixtures"
```

---

### Task 5: 비밀번호 해싱

**Files:**
- Create: `backend/app/auth/__init__.py` (빈), `backend/app/auth/passwords.py`
- Create: `backend/tests/test_passwords.py`

- [ ] **Step 1: 빈 `__init__.py`**

`backend/app/auth/__init__.py` (내용 없음).

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_passwords.py`:
```python
from app.auth.passwords import hash_password, verify_password


def test_hash_password_returns_different_hash_each_time():
    h1 = hash_password("hunter2")
    h2 = hash_password("hunter2")
    assert h1 != h2  # argon2는 salt가 매번 달라 같은 비밀번호도 다른 해시


def test_verify_password_accepts_correct():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True


def test_verify_password_rejects_wrong():
    h = hash_password("hunter2")
    assert verify_password("wrong", h) is False


def test_verify_password_handles_garbage_hash():
    assert verify_password("anything", "not-a-real-hash") is False
```

- [ ] **Step 3: 실패 확인**

```powershell
cd backend
uv run pytest tests/test_passwords.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: 구현**

`backend/app/auth/passwords.py`:
```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        _hasher.verify(hashed, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False
```

- [ ] **Step 5: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_passwords.py -v
```
Expected: 4 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): argon2 password hashing"
```

---

### Task 6: JWT 토큰 모듈

**Files:**
- Create: `backend/app/auth/tokens.py`
- Create: `backend/tests/test_tokens.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_tokens.py`:
```python
import time

import pytest
from jose import JWTError

from app.auth.tokens import (
    encode_access_token,
    decode_access_token,
    generate_refresh_token_id,
)


SECRET = "test-secret"


def test_encode_decode_round_trip():
    token = encode_access_token(user_id=42, secret=SECRET, ttl_seconds=60)
    payload = decode_access_token(token, SECRET)
    assert payload["sub"] == "42"


def test_decode_with_wrong_secret_raises():
    token = encode_access_token(42, SECRET, 60)
    with pytest.raises(JWTError):
        decode_access_token(token, "wrong-secret")


def test_decode_expired_token_raises():
    token = encode_access_token(42, SECRET, ttl_seconds=-1)  # 이미 만료
    with pytest.raises(JWTError):
        decode_access_token(token, SECRET)


def test_generate_refresh_token_id_is_unique():
    ids = {generate_refresh_token_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(i) == 32 for i in ids)  # uuid4 hex = 32자
```

- [ ] **Step 2: 실패 확인**

```powershell
uv run pytest tests/test_tokens.py -v
```
Expected: FAIL.

- [ ] **Step 3: 구현**

`backend/app/auth/tokens.py`:
```python
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt


_ALGO = "HS256"


def encode_access_token(user_id: int, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGO)


def decode_access_token(token: str, secret: str) -> dict:
    """python-jose는 만료/위조 등에서 JWTError 또는 그 서브클래스를 raise."""
    return jwt.decode(token, secret, algorithms=[_ALGO])


def generate_refresh_token_id() -> str:
    return uuid.uuid4().hex
```

- [ ] **Step 4: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_tokens.py -v
```
Expected: 4 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): JWT access tokens + refresh token id"
```

---

### Task 7: Redis 클라이언트 + refresh-token 헬퍼

**Files:**
- Create: `backend/app/redis_client.py`
- Modify: `backend/tests/conftest.py` (fakeredis 픽스처 추가)
- Create: `backend/tests/test_redis_client.py`

- [ ] **Step 1: `conftest.py`에 fakeredis 픽스처 추가**

`backend/tests/conftest.py` 끝에 추가:
```python
@pytest.fixture(autouse=True)
async def _fake_redis(monkeypatch):
    """모든 테스트에서 실제 Redis 대신 fakeredis 사용."""
    import fakeredis.aioredis
    from app import redis_client

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_redis", fake)
    yield
    await fake.aclose()
```

(이 픽스처는 `app.redis_client._redis` 모듈 변수를 fakeredis로 대체.)

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_redis_client.py`:
```python
import pytest

from app import redis_client


@pytest.mark.anyio
async def test_store_and_get_refresh_token():
    await redis_client.store_refresh_token("tok-1", user_id=7, ttl=60)
    user_id = await redis_client.get_user_for_refresh("tok-1")
    assert user_id == 7


@pytest.mark.anyio
async def test_get_user_for_refresh_returns_none_for_missing():
    assert await redis_client.get_user_for_refresh("missing") is None


@pytest.mark.anyio
async def test_delete_refresh_token():
    await redis_client.store_refresh_token("tok-2", user_id=7, ttl=60)
    await redis_client.delete_refresh_token("tok-2")
    assert await redis_client.get_user_for_refresh("tok-2") is None
```

- [ ] **Step 3: 실패 확인**

```powershell
uv run pytest tests/test_redis_client.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.redis_client'`.

- [ ] **Step 4: 구현**

`backend/app/redis_client.py`:
```python
import redis.asyncio as redis

from app.config import settings


# 모듈 수준 클라이언트 — lifespan에서 init/close.
_redis: redis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> redis.Redis:
    if _redis is None:
        raise RuntimeError("Redis client not initialized (call init_redis first)")
    return _redis


# refresh token 헬퍼들 — 키 컨벤션: `refresh:{token_id}` → value = user_id (str), TTL = jwt_refresh_ttl_seconds.

async def store_refresh_token(token_id: str, user_id: int, ttl: int) -> None:
    await get_redis().set(f"refresh:{token_id}", str(user_id), ex=ttl)


async def get_user_for_refresh(token_id: str) -> int | None:
    val = await get_redis().get(f"refresh:{token_id}")
    return int(val) if val is not None else None


async def delete_refresh_token(token_id: str) -> None:
    await get_redis().delete(f"refresh:{token_id}")
```

- [ ] **Step 5: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_redis_client.py -v
```
Expected: 3 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): redis client + refresh token helpers"
```

---

### Task 8: Lifespan — `main.py`에서 DB 마이그레이션 + Redis init 연결

**Files:**
- Modify: `backend/app/main.py`
- Modify: 기존 `backend/tests/test_health.py` (회귀 확인 — TestClient가 lifespan 정상 동작하는지)

- [ ] **Step 1: `main.py` 수정**

`backend/app/main.py` 전체를 아래로 교체:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.engine import engine
from app.db.migrate import apply_migrations
from app.redis_client import close_redis, init_redis
from app.routers import stocks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작: DB 마이그레이션, Redis 연결
    await apply_migrations(engine)
    await init_redis()
    yield
    # 종료: Redis 닫고 엔진 dispose
    await close_redis()
    await engine.dispose()


app = FastAPI(title="KIS Stock Scaffold", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],  # 이전엔 ["GET"]뿐 — auth가 POST라 추가
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(stocks.router)
```

- [ ] **Step 2: 회귀 테스트 실행 — 기존 모든 테스트 통과해야 함**

```powershell
cd backend
uv run pytest -v
```
Expected: 기존 + Task 2~7에서 추가한 테스트 전부 PASS. lifespan이 TestClient 안에서 정상 동작(DB 마이그레이션 + fakeredis 셋업)해야 함.

만약 `test_health.py`가 실패하면 — TestClient가 lifespan을 부르는데, conftest의 `_fake_redis` 픽스처가 lifespan의 `init_redis()`를 덮어쓰는지 확인. (autouse 픽스처는 fixture setup 단계에서 적용되고, TestClient의 lifespan은 `with TestClient(app) as client:`처럼 enter 시점에 실행됨. `TestClient(app)`를 컨텍스트 매니저로 안 쓰면 lifespan이 자동 실행되지 않을 수 있음 — Starlette 동작.)

> **중요:** Starlette의 TestClient는 `with TestClient(app) as client:` 형태로 써야 lifespan이 동작함. 그냥 `client = TestClient(app)`만 하면 lifespan이 안 돎. 따라서 기존 `test_health.py`의 `client = TestClient(app)`를 lifespan에 의존하게 두려면 `with` 형태로 바꿔야 함. **현재 health 라우트는 DB/Redis 안 쓰니까 lifespan이 안 돌아도 OK** — 기존 코드 안 건드림.

- [ ] **Step 3: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): app lifespan with DB migrate + redis init, CORS POST"
```

---

### Task 9: Pydantic 스키마 + Register 엔드포인트

**Files:**
- Create: `backend/app/schemas/__init__.py` (빈), `backend/app/schemas/auth.py`
- Create: `backend/app/auth/service.py`, `backend/app/routers/auth.py`
- Modify: `backend/app/main.py` (auth router include)
- Create: `backend/tests/test_auth_register.py`

- [ ] **Step 1: 빈 `__init__.py`**

`backend/app/schemas/__init__.py` (내용 없음).

- [ ] **Step 2: 스키마 작성**

`backend/app/schemas/auth.py`:
```python
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 3: 실패하는 테스트 작성**

`backend/tests/test_auth_register.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_register_creates_user_and_returns_201():
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "hunter22"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email():
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "hunter22"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "password": "different8"},
        )
    assert resp.status_code == 409


def test_register_rejects_short_password():
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/register",
            json={"email": "short@example.com", "password": "short"},
        )
    assert resp.status_code == 422  # pydantic validation


def test_register_rejects_invalid_email():
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "hunter22"},
        )
    assert resp.status_code == 422
```

- [ ] **Step 4: 실패 확인**

```powershell
cd backend
uv run pytest tests/test_auth_register.py -v
```
Expected: FAIL — 라우트 404 또는 모듈 없음.

- [ ] **Step 5: 서비스 + 라우터 구현**

`backend/app/auth/service.py`:
```python
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import encode_access_token, generate_refresh_token_id
from app.config import settings
from app.db.queries import users as users_q
from app.db.queries.users import User
from app.redis_client import (
    delete_refresh_token,
    get_user_for_refresh,
    store_refresh_token,
)


class AuthError(Exception):
    """Auth 도메인 예외 베이스."""


class EmailAlreadyExists(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidRefreshToken(AuthError):
    pass


async def register(conn: AsyncConnection, email: str, password: str) -> User:
    existing = await users_q.get_user_by_email(conn, email)
    if existing:
        raise EmailAlreadyExists(email)
    pwd_hash = hash_password(password)
    try:
        return await users_q.create_user(conn, email, pwd_hash)
    except IntegrityError as e:
        # 동시 가입 등 race condition 대비
        raise EmailAlreadyExists(email) from e
```

`backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth import service as auth_service
from app.db.engine import get_conn
from app.schemas.auth import RegisterRequest, UserResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    req: RegisterRequest,
    conn: AsyncConnection = Depends(get_conn),
) -> UserResponse:
    try:
        user = await auth_service.register(conn, req.email, req.password)
    except auth_service.EmailAlreadyExists:
        raise HTTPException(status_code=409, detail="Email already exists")
    return UserResponse(id=user.id, email=user.email)
```

`backend/app/main.py`에 auth router 추가 — 기존 `include_router(stocks.router)` 아래에 한 줄:
```python
from app.routers import auth as auth_router  # 파일 상단 import 모음에 추가
...
app.include_router(auth_router.router)
```

- [ ] **Step 6: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_auth_register.py -v
```
Expected: 4 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): POST /api/auth/register"
```

---

### Task 10: Login 엔드포인트

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_login.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth_login.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def _register(client, email="user@example.com", password="hunter22"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_login_returns_tokens():
    with TestClient(app) as client:
        _register(client)
        resp = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "hunter22"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert len(body["refresh_token"]) == 32  # uuid4 hex


def test_login_rejects_wrong_password():
    with TestClient(app) as client:
        _register(client)
        resp = client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrongword"},
        )
    assert resp.status_code == 401


def test_login_rejects_unknown_email():
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "hunter22"},
        )
    assert resp.status_code == 401
```

- [ ] **Step 2: 실패 확인**

```powershell
cd backend
uv run pytest tests/test_auth_login.py -v
```
Expected: FAIL — `/api/auth/login` 없음(404).

- [ ] **Step 3: 서비스 함수 추가**

`backend/app/auth/service.py` 끝에 추가:
```python
async def login(conn: AsyncConnection, email: str, password: str) -> tuple[str, str]:
    """성공 시 (access_token, refresh_token_id) 반환."""
    user = await users_q.get_user_by_email(conn, email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    access = encode_access_token(
        user_id=user.id,
        secret=settings.jwt_secret,
        ttl_seconds=settings.jwt_access_ttl_seconds,
    )
    refresh_id = generate_refresh_token_id()
    await store_refresh_token(
        refresh_id, user_id=user.id, ttl=settings.jwt_refresh_ttl_seconds
    )
    return access, refresh_id
```

- [ ] **Step 4: 라우터에 엔드포인트 추가**

`backend/app/routers/auth.py`에 import 추가하고 끝에:
```python
# 파일 상단 import 보강:
from app.schemas.auth import RegisterRequest, UserResponse, LoginRequest, TokenResponse

# 끝에 추가:
@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    conn: AsyncConnection = Depends(get_conn),
) -> TokenResponse:
    try:
        access, refresh = await auth_service.login(conn, req.email, req.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=access, refresh_token=refresh)
```

- [ ] **Step 5: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_auth_login.py -v
```
Expected: 3 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): POST /api/auth/login with JWT + redis refresh"
```

---

### Task 11: Refresh 엔드포인트 (rotation)

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_refresh.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth_refresh.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def _register_and_login(client, email="r@example.com", password="hunter22"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()


def test_refresh_rotates_token():
    with TestClient(app) as client:
        tokens = _register_and_login(client)
        old_refresh = tokens["refresh_token"]

        resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        new = resp.json()
        assert new["access_token"] != tokens["access_token"] or True  # 같을 수도(같은 초 내) 다를 수도 — 단언 안 함
        assert new["refresh_token"] != old_refresh  # rotation: 반드시 새 refresh


def test_refresh_old_token_invalidated_after_rotation():
    with TestClient(app) as client:
        tokens = _register_and_login(client)
        old_refresh = tokens["refresh_token"]
        # 한 번 갱신 — 옛 refresh는 무효화돼야 함
        client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        # 옛 refresh로 다시 시도 → 401
        resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401


def test_refresh_with_invalid_token():
    with TestClient(app) as client:
        resp = client.post("/api/auth/refresh", json={"refresh_token": "garbage"})
        assert resp.status_code == 401
```

- [ ] **Step 2: 실패 확인**

```powershell
cd backend
uv run pytest tests/test_auth_refresh.py -v
```
Expected: FAIL — `/api/auth/refresh` 없음.

- [ ] **Step 3: 서비스 함수 추가**

`backend/app/auth/service.py` 끝에 추가:
```python
async def refresh(refresh_token_id: str) -> tuple[str, str]:
    """성공 시 (new_access_token, new_refresh_token_id) 반환. 옛 refresh는 무효화."""
    user_id = await get_user_for_refresh(refresh_token_id)
    if user_id is None:
        raise InvalidRefreshToken()
    # rotation: 옛 거 즉시 무효
    await delete_refresh_token(refresh_token_id)
    new_refresh_id = generate_refresh_token_id()
    await store_refresh_token(
        new_refresh_id, user_id=user_id, ttl=settings.jwt_refresh_ttl_seconds
    )
    new_access = encode_access_token(
        user_id=user_id,
        secret=settings.jwt_secret,
        ttl_seconds=settings.jwt_access_ttl_seconds,
    )
    return new_access, new_refresh_id
```

- [ ] **Step 4: 라우터 추가**

`backend/app/routers/auth.py` import 보강 + 엔드포인트:
```python
# import:
from app.schemas.auth import RegisterRequest, UserResponse, LoginRequest, TokenResponse, RefreshRequest

# 끝:
@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest) -> TokenResponse:
    try:
        access, new_refresh = await auth_service.refresh(req.refresh_token)
    except auth_service.InvalidRefreshToken:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return TokenResponse(access_token=access, refresh_token=new_refresh)
```

- [ ] **Step 5: 통과 확인 + 커밋**

```powershell
uv run pytest tests/test_auth_refresh.py -v
```
Expected: 3 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): POST /api/auth/refresh with token rotation"
```

---

### Task 12: Logout 엔드포인트

**Files:**
- Modify: `backend/app/auth/service.py`, `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_logout.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth_logout.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_logout_invalidates_refresh_token():
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"email": "lo@example.com", "password": "hunter22"})
        tokens = client.post(
            "/api/auth/login", json={"email": "lo@example.com", "password": "hunter22"}
        ).json()
        refresh = tokens["refresh_token"]

        # 로그아웃
        resp = client.post("/api/auth/logout", json={"refresh_token": refresh})
        assert resp.status_code == 204

        # 그 refresh로 갱신 시도 → 401
        r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code == 401


def test_logout_with_unknown_token_still_204():
    """이미 사라진 토큰으로 로그아웃 호출해도 멱등하게 204."""
    with TestClient(app) as client:
        resp = client.post("/api/auth/logout", json={"refresh_token": "anything"})
        assert resp.status_code == 204
```

- [ ] **Step 2: 실패 확인**

```powershell
uv run pytest tests/test_auth_logout.py -v
```
Expected: FAIL — `/api/auth/logout` 없음.

- [ ] **Step 3: 서비스 함수 추가**

`backend/app/auth/service.py` 끝:
```python
async def logout(refresh_token_id: str) -> None:
    """멱등 — 없는 토큰이어도 에러 안 냄."""
    await delete_refresh_token(refresh_token_id)
```

- [ ] **Step 4: 라우터 추가**

`backend/app/routers/auth.py`:
```python
@router.post("/logout", status_code=204)
async def logout(req: RefreshRequest) -> None:
    await auth_service.logout(req.refresh_token)
```

- [ ] **Step 5: 통과 + 커밋**

```powershell
uv run pytest tests/test_auth_logout.py -v
```
Expected: 2 passed.

```powershell
cd ..
git add backend
git commit -m "feat(backend): POST /api/auth/logout (idempotent)"
```

---

### Task 13: `get_current_user` 의존성 + `GET /api/auth/me`

**Files:**
- Create: `backend/app/auth/dependencies.py`
- Modify: `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_me.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_auth_me.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_me_returns_current_user():
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"email": "me@example.com", "password": "hunter22"})
        tokens = client.post(
            "/api/auth/login", json={"email": "me@example.com", "password": "hunter22"}
        ).json()

        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_me_without_token_returns_401():
    with TestClient(app) as client:
        resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_returns_401():
    with TestClient(app) as client:
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
        )
    assert resp.status_code == 401
```

- [ ] **Step 2: 실패 확인**

```powershell
uv run pytest tests/test_auth_me.py -v
```
Expected: FAIL.

- [ ] **Step 3: 의존성 구현**

`backend/app/auth/dependencies.py`:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.tokens import decode_access_token
from app.config import settings
from app.db.engine import get_conn
from app.db.queries import users as users_q
from app.db.queries.users import User


# tokenUrl은 OpenAPI Swagger UI에서 자동 로그인 폼에 쓰임 — 우리 /login은 JSON이라 정확히 호환은 안 되지만 OK.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: AsyncConnection = Depends(get_conn),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token, settings.jwt_secret)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exc
    user = await users_q.get_user_by_id(conn, user_id)
    if user is None:
        raise credentials_exc
    return user
```

- [ ] **Step 4: `/me` 라우트 추가**

`backend/app/routers/auth.py`에 import + 라우트:
```python
# import:
from app.auth.dependencies import get_current_user
from app.db.queries.users import User

# 끝:
@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=current_user.id, email=current_user.email)
```

- [ ] **Step 5: 전체 백엔드 테스트 통과 확인**

```powershell
uv run pytest -v
```
Expected: 기존 11개 + 이번 단계에서 추가된 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```powershell
cd ..
git add backend
git commit -m "feat(backend): get_current_user dep + GET /api/auth/me"
```

---

### Task 14: 프론트 — auth 라이브러리 + api.ts 확장

**Files:**
- Create: `frontend/src/app/lib/auth.tsx`
- Modify: `frontend/src/app/lib/api.ts`

- [ ] **Step 1: `auth.tsx` 작성**

`frontend/src/app/lib/auth.tsx`:
```tsx
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const ACCESS_KEY = "auth.access";
const REFRESH_KEY = "auth.refresh";

export interface AuthUser {
  id: number;
  email: string;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ──────────────────────────────────────
// 토큰 저장 헬퍼 (localStorage)
// ──────────────────────────────────────
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// ──────────────────────────────────────
// 백엔드 호출
// ──────────────────────────────────────
async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => null);
    throw new Error(detail ?? `${path} 실패 (${res.status})`);
  }
  return (await res.json()) as T;
}

export async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const { access_token, refresh_token } = await postJson<{
      access_token: string;
      refresh_token: string;
    }>("/api/auth/refresh", { refresh_token: refresh });
    setTokens(access_token, refresh_token);
    return access_token;
  } catch {
    clearTokens();
    return null;
  }
}

// ──────────────────────────────────────
// Context Provider
// ──────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  const fetchMe = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setState({ user: null, loading: false });
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        // access 만료 → refresh 시도
        const newAccess = await refreshAccessToken();
        if (!newAccess) {
          setState({ user: null, loading: false });
          return;
        }
        const retry = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${newAccess}` },
        });
        if (!retry.ok) {
          setState({ user: null, loading: false });
          return;
        }
        const user = (await retry.json()) as AuthUser;
        setState({ user, loading: false });
        return;
      }
      if (!res.ok) {
        setState({ user: null, loading: false });
        return;
      }
      const user = (await res.json()) as AuthUser;
      setState({ user, loading: false });
    } catch {
      setState({ user: null, loading: false });
    }
  }, []);

  useEffect(() => {
    void fetchMe();
  }, [fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token, refresh_token } = await postJson<{
        access_token: string;
        refresh_token: string;
      }>("/api/auth/login", { email, password });
      setTokens(access_token, refresh_token);
      await fetchMe();
    },
    [fetchMe],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await postJson<AuthUser>("/api/auth/register", { email, password });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await postJson("/api/auth/logout", { refresh_token: refresh });
      } catch {
        // 무시 — 클라이언트는 어쨌든 토큰 버림
      }
    }
    clearTokens();
    setState({ user: null, loading: false });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, register, logout }),
    [state, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
```

- [ ] **Step 2: `api.ts`를 인증-aware로 확장**

`frontend/src/app/lib/api.ts` 전체를 아래로 교체:
```ts
import { getAccessToken, refreshAccessToken } from "@/app/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface StockPrice {
  code: string;
  name: string;
  price: number;
  change: number;
  change_rate: number;
  volume: number;
}

/** access 토큰을 헤더에 첨부하고, 401이면 refresh 후 1회 재시도하는 fetch. */
async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers, cache: "no-store" });
  if (res.status !== 401) return res;

  const newAccess = await refreshAccessToken();
  if (!newAccess) return res;
  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${newAccess}`);
  return fetch(input, { ...init, headers: retryHeaders, cache: "no-store" });
}

export async function fetchPrice(code: string): Promise<StockPrice> {
  const res = await authedFetch(`${API_BASE}/api/stocks/${code}/price`);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `요청 실패 (${res.status})`);
  }
  return (await res.json()) as StockPrice;
}
```

- [ ] **Step 3: 검증 — lint + build**

```powershell
cd frontend
pnpm lint
pnpm build
```
Expected: lint pass, build success.

- [ ] **Step 4: 커밋**

```powershell
cd ..
git add frontend
git commit -m "feat(frontend): AuthContext, token storage, authed fetch with 401 retry"
```

---

### Task 15: 프론트 — 로그인/회원가입 페이지 + 레이아웃 통합

**Files:**
- Create: `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/app/(auth)/register/page.tsx`
- Modify: `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`

- [ ] **Step 1: 디렉터리 만들기**

```powershell
New-Item -ItemType Directory -Force frontend/src/app/(auth) | Out-Null
New-Item -ItemType Directory -Force "frontend/src/app/(auth)/login" | Out-Null
New-Item -ItemType Directory -Force "frontend/src/app/(auth)/register" | Out-Null
```

(`(auth)`는 Next.js App Router의 route group — URL에 영향 안 줌, 그룹화용.)

- [ ] **Step 2: 로그인 페이지**

`frontend/src/app/(auth)/login/page.tsx`:
```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/app/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-bold">로그인</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <input
          type="email"
          placeholder="이메일"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded border px-3 py-2"
        />
        <input
          type="password"
          placeholder="비밀번호 (8자 이상)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          className="rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>
      {error && <p className="mt-4 text-red-600">{error}</p>}
      <p className="mt-4 text-sm">
        계정 없어요? <Link href="/register" className="text-blue-600 underline">회원가입</Link>
      </p>
    </main>
  );
}
```

- [ ] **Step 3: 회원가입 페이지**

`frontend/src/app/(auth)/register/page.tsx`:
```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/app/lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "회원가입 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm p-8">
      <h1 className="mb-6 text-2xl font-bold">회원가입</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <input
          type="email"
          placeholder="이메일"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded border px-3 py-2"
        />
        <input
          type="password"
          placeholder="비밀번호 (8자 이상)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          className="rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "가입 중..." : "가입"}
        </button>
      </form>
      {error && <p className="mt-4 text-red-600">{error}</p>}
      <p className="mt-4 text-sm">
        이미 계정 있어요? <Link href="/login" className="text-blue-600 underline">로그인</Link>
      </p>
    </main>
  );
}
```

- [ ] **Step 4: `layout.tsx`에 AuthProvider 래핑**

`frontend/src/app/layout.tsx` (이미 있는 파일 수정 — 아래는 전체 모습. 기존 파일의 폰트/메타 import는 유지하고 `body` 내부만 AuthProvider로 감싸기):
```tsx
import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/app/lib/auth";

export const metadata: Metadata = {
  title: "side — KIS 주식 챗봇",
  description: "한국투자증권 모의투자 + LLM 챗봇",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

> 메모: `create-next-app`이 만든 layout.tsx에 폰트(`Geist` 등) 설정이 들어있을 수 있음. 그 부분은 유지하고 `<body>` 자식만 `<AuthProvider>{children}</AuthProvider>` 로 감싸기.

- [ ] **Step 5: 홈 페이지에서 로그인 상태 표시**

`frontend/src/app/page.tsx` 상단에 — 기존 종목 조회 UI 그대로 두고, 맨 위에 작은 헤더 추가. 파일 전체:
```tsx
"use client";

import Link from "next/link";
import { useState } from "react";

import { fetchPrice, type StockPrice } from "@/app/lib/api";
import { useAuth } from "@/app/lib/auth";

export default function Home() {
  const { user, loading: authLoading, logout } = useAuth();
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
      <div className="mb-6 flex items-center justify-between text-sm">
        {authLoading ? (
          <span className="text-gray-500">확인 중...</span>
        ) : user ? (
          <>
            <span>안녕하세요, <strong>{user.email}</strong></span>
            <button onClick={logout} className="text-blue-600 underline">로그아웃</button>
          </>
        ) : (
          <span>
            <Link href="/login" className="text-blue-600 underline">로그인</Link>
            {" · "}
            <Link href="/register" className="text-blue-600 underline">회원가입</Link>
          </span>
        )}
      </div>

      <h1 className="mb-6 text-2xl font-bold">국내주식 현재가 조회 (모의투자)</h1>
      <form onSubmit={onSubmit} className="mb-6 flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="종목코드 (예: 005930)"
          aria-label="종목코드"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading || !code.trim()}
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

- [ ] **Step 6: 린트 + 빌드**

```powershell
cd frontend
pnpm lint
pnpm build
```
Expected: lint pass, build success.

- [ ] **Step 7: 커밋**

```powershell
cd ..
git add frontend
git commit -m "feat(frontend): login/register pages + AuthProvider in layout"
```

---

### Task 16: 수동 end-to-end 검증

**Files:** (변경 없음 — 검증 단계)

- [ ] **Step 1: 인프라 기동 확인**

```powershell
docker compose ps
```
Expected: postgres + redis 둘 다 `healthy`. 아니면 `docker compose up -d`.

- [ ] **Step 2: 백엔드 기동**

새 터미널:
```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```
콘솔에 `INFO: Application startup complete.` 떠야 함 (lifespan에서 마이그레이션 + Redis 연결 성공).

- [ ] **Step 3: 백엔드 헬스 + 가입/로그인 cURL**

또 다른 터미널:
```powershell
curl http://localhost:8000/api/health
# {"status":"ok"}

curl -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d '{"email":"e2e@example.com","password":"hunter22"}'
# {"id":1,"email":"e2e@example.com"}

curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"email":"e2e@example.com","password":"hunter22"}'
# {"access_token":"...","refresh_token":"...","token_type":"bearer"}
```

(PowerShell 에서 위 cURL이 까다로우면 `curl.exe`를 명시하거나 Invoke-RestMethod 사용.)

- [ ] **Step 4: 프론트 기동**

또 다른 터미널:
```powershell
cd frontend
pnpm dev
```
http://localhost:3000 접속.

- [ ] **Step 5: UI 플로우 확인**

1. `/register` 페이지 → 새 이메일·비번 입력 → 가입 → `/`로 이동 → "안녕하세요, ..." 보임.
2. 로그아웃 클릭 → 헤더가 "로그인 · 회원가입"으로 바뀜.
3. `/login` 페이지 → 같은 이메일/비번 → 로그인 → 다시 인사 메시지.
4. 페이지 새로고침 → 여전히 로그인 상태 유지 (localStorage에서 access 토큰 복원, /me 호출 성공).
5. localStorage에서 `auth.access`만 지우고 새로고침 → refresh로 자동 재로그인 → 인사 메시지 유지.
6. 둘 다 지우고 새로고침 → 로그아웃 상태.

- [ ] **Step 6: 전체 백엔드 테스트 재실행 — 모두 통과 확인**

```powershell
cd backend
uv run pytest -v
```
Expected: ALL PASS (기존 11개 + 이번 단계에서 추가된 회원가입/로그인/갱신/로그아웃/me/passwords/tokens/redis/queries/config/migrate).

- [ ] **Step 7: 최종 커밋 (필요 시)**

위 단계에서 README 등 보완할 게 있으면 수정 후:
```powershell
cd ..
git add -A
git commit -m "docs: stage 1 auth foundation complete"
```
변경 없으면 생략.

---

## Self-Review

**1. Spec coverage** — 설계 문서 단계 1 요구사항을 작업으로 매핑:
- Postgres 연결 + users 테이블 + 마이그레이션 → Task 3 ✓
- Redis 연결 → Task 7 (헬퍼) + Task 8 (lifespan) ✓
- 회원가입 + 비밀번호 해싱 → Task 5 (passwords) + Task 9 (register) ✓
- 로그인 + JWT 발급 + refresh token Redis 저장 → Task 6 (tokens) + Task 7 (redis 헬퍼) + Task 10 (login) ✓
- 토큰 갱신 + rotation → Task 11 ✓
- 로그아웃 + Redis 삭제 → Task 12 ✓
- 인증 의존성 (`Depends`) + 현재 사용자 주입 → Task 13 ✓
- 보호된 라우트 적용 — `/me` 가 카나리아 → Task 13 ✓
- 프론트 로그인/회원가입 페이지 + 토큰 저장 + 인증된 fetch 래퍼 + 보호된 라우트 가드 → Task 14, 15 ✓ (라우트 가드는 home에서 user 상태 분기로 간단 구현; 본격적인 middleware 가드는 단계 2에서 챗봇 페이지 보호할 때 추가 가능 — 설계에 명시되진 않았지만 충분)
- 테스트: 가입→로그인→갱신→로그아웃 + 만료/위조 토큰 + fakeredis + 테스트 DB → Task 4, 5, 6, 7, 9, 10, 11, 12, 13 ✓
- 설계 "열린 질문" 중 단계 1 해당분: 마이그레이션 도구(번호 .sql 채택, Task 3), 로그인=이메일/비밀번호만 (Task 9 — OAuth 안 함, 단계 1 범위 밖), 프론트 토큰 저장=localStorage + 401 retry (Task 14 — README/스펙에 트레이드오프 명시 필요. 본 plan 헤더의 "Architecture" 줄에서 "401 응답 시 refresh 자동 호출"로 기록됨. 보안 트레이드오프는 단계 2에서 다시 검토 가능).

빠진 거 없음.

**2. Placeholder scan** — "TBD", "TODO", "구현 나중에", "적절히 처리" 류 없음. 모든 코드 스텝에 실제 코드. 마이그레이션 도구 결정도 명시(번호 .sql + 러너). ✓

**3. Type consistency** —
- `User` dataclass (id: int, email: str, password_hash: str) — Task 4 정의, Task 9 (service.register 반환), Task 13 (get_current_user 반환), Task 10/11 (service 내부 사용) 모두 일관. ✓
- `auth_service` 예외: `AuthError`, `EmailAlreadyExists`, `InvalidCredentials`, `InvalidRefreshToken` — Task 9 정의, 이후 Task 10/11/13 라우터에서 정확히 같은 이름으로 catch. ✓
- redis 헬퍼: `store_refresh_token`, `get_user_for_refresh`, `delete_refresh_token` — Task 7 정의, service 모듈(Task 9~12)에서 일치. ✓
- token 함수: `encode_access_token(user_id, secret, ttl_seconds)`, `decode_access_token(token, secret)`, `generate_refresh_token_id()` — Task 6 정의, service/dependencies에서 일치. ✓
- pydantic 스키마: `RegisterRequest`/`UserResponse`/`LoginRequest`/`TokenResponse`/`RefreshRequest` — Task 9 정의, Task 10/11/12/13 import 일치. ✓
- 프론트 `useAuth` 반환 형태: `user, loading, login, register, logout` — Task 14 정의, Task 15 (login/register/home) 사용 일치. `AuthUser = {id, email}` — `/me` 응답(`UserResponse`)과 키 일치. ✓
- API 베이스 URL 변수명 `NEXT_PUBLIC_API_BASE_URL` — 기존 `.env.local.example`, 새 `auth.tsx`, 새 `api.ts` 모두 일치. ✓

이슈 없음.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-auth-foundation.md`.

두 가지 실행 옵션:

**1. Subagent-Driven (추천)** — 작업마다 새 서브에이전트가 구현 → 스펙 리뷰 → 코드 품질 리뷰. 빠르게.

**2. Inline Execution** — 이 세션에서 직접 작업들을 배치로 실행, 체크포인트에서 멈춰서 리뷰.

어느 쪽으로?
