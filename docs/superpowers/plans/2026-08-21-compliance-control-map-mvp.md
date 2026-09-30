# Compliance Control Map MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superjawn:subagent-driven-development (recommended) or superjawn:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-quality, self-hosted compliance readiness and evidence workspace with a SOC 2 framework map, organizational controls, reusable documents/evidence, local and team deployment modes, and a reserved provider-neutral inference seam.

**Architecture:** A React/TypeScript/Vite SPA talks only to a versioned FastAPI REST API. The modular FastAPI application uses SQLAlchemy/Alembic against SQLite or PostgreSQL and a `FileStorage` protocol for artifact bytes; framework catalog data is immutable and workspace assessment/control/evidence state is separate. Docker Compose exposes a same-origin app at port 3000, with project-local launchers handling migrations, seed data, persistence, and safe local refresh.

**Tech Stack:** React 19, TypeScript, Vite, React Router, TanStack Query, Vitest, Testing Library, Playwright; Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, Argon2id, pytest; SQLite, PostgreSQL, Docker Compose, Nginx.

---

## Execution context

Run every task from:

```text
C:\Users\lhp21\Documents\codexproject\ComplianceControl\.worktrees\compliance-control-mvp
```

Never configure a Git remote or push. Commit only to the local `feature/compliance-control-mvp` branch.

## Scope decomposition

The product contains several modules, but they are not independently useful deployments: the map requires assessments, uploads require mappings, and dashboard values require the shared domain model. This plan therefore uses four testable vertical phases inside one plan:

1. Foundation and immutable framework catalog
2. Authenticated assessment/control/evidence API
3. Field Manual web experience
4. Packaging, backup, hardening, and end-to-end verification

Each task leaves the application or a module in a runnable, tested state.

## File responsibility map

### Root and operations

- `AGENTS.md` — repository rules, verification commands, architecture boundaries, and explicit AI/V1 scope.
- `.env.example` — documented runtime configuration with safe local defaults.
- `docker-compose.yml` — local web/API stack with named SQLite and file volumes.
- `docker-compose.server.yml` — PostgreSQL/team-mode overlay using the same images.
- `launch.ps1`, `launch.sh` — non-developer start/status/refresh/restore entrypoints.
- `README.md` — quick start, deployment, security, backup, framework-pack, and development guide.
- `framework-packs/soc2/` — immutable source-controlled SOC 2 pack and validation metadata.
- `agents/`, `skills/` — documented, disabled future inference conventions; no runtime integration.

### Backend

- `backend/pyproject.toml` — backend runtime/dev dependencies and test/lint configuration.
- `backend/alembic.ini`, `backend/alembic/` — one migration history for SQLite and PostgreSQL.
- `backend/app/main.py` — application factory and middleware assembly only.
- `backend/app/core/` — settings, errors, security headers, request IDs, database/session lifecycle.
- `backend/app/models/` — focused SQLAlchemy model modules and association records.
- `backend/app/schemas/` — Pydantic request/response contracts grouped by resource.
- `backend/app/services/` — domain transactions and calculations; routers remain thin.
- `backend/app/api/v1/` — versioned resource routers and authorization dependencies.
- `backend/app/storage/` — storage protocol and local filesystem implementation.
- `backend/app/inference/` — disabled protocol definitions only.
- `backend/tests/` — unit, service, API, security, migration, and storage tests.

### Frontend

- `frontend/package.json`, `pnpm-lock.yaml` — reproducible browser toolchain.
- `frontend/src/app/` — router, providers, API client, session state, shell.
- `frontend/src/design/` — Field Manual tokens, typography, global styles, primitives.
- `frontend/src/features/dashboard/` — readiness ledger and action queues.
- `frontend/src/features/framework-map/` — generic domains, roving keyboard navigation, filters, tiles, detail sheet.
- `frontend/src/features/tracker/` — semantic sortable table and inline assessment updates.
- `frontend/src/features/libraries/` — documents/evidence lists, upload, mapping, details.
- `frontend/src/features/settings/` — workspace/users/export/framework information.
- `frontend/src/test/` — test setup, accessibility helpers, API fixtures.
- `frontend/e2e/` — browser acceptance workflow.

---

## Phase 1 — Foundation and framework catalog

### Task 1: Establish the backend and frontend test harnesses

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/v1/health.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/eslint.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Write the failing API health test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_returns_stable_envelope() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}, "meta": {}}
```

- [ ] **Step 2: Run the backend test and verify the missing application fails**

Run from `backend/`:

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests/test_health.py -q
```

Expected: collection fails because `app.main.create_app` does not exist.

- [ ] **Step 3: Add the minimal FastAPI application and exact dependency configuration**

```python
# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Compliance Control Map API", version="0.1.0")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
```

```python
# backend/app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, object]:
    return {"data": {"status": "ok"}, "meta": {}}
```

Use this exact initial backend configuration:

```toml
# backend/pyproject.toml
[build-system]
requires = ["setuptools==80.9.0"]
build-backend = "setuptools.build_meta"

[project]
name = "compliance-control-map-api"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = [
  "alembic==1.19.0",
  "argon2-cffi==25.1.0",
  "email-validator==2.3.0",
  "fastapi==0.141.1",
  "filetype==1.2.0",
  "psycopg[binary]==3.3.4",
  "pydantic==2.13.4",
  "pydantic-settings==2.15.0",
  "python-multipart==0.0.32",
  "PyYAML==6.0.3",
  "SQLAlchemy==2.0.51",
  "uvicorn==0.51.0",
]

[project.optional-dependencies]
dev = [
  "httpx2==2.9.1",
  "mypy==1.19.1",
  "pytest==9.0.2",
  "pytest-cov==7.0.0",
  "ruff==0.14.11",
  "time-machine==3.2.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --strict-config"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "SIM", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]
```

- [ ] **Step 4: Add and run the minimal React rendering test**

```tsx
// frontend/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("names the workspace", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Compliance Control Map" })).toBeVisible();
  });
});
```

Use this exact initial frontend package contract, then commit the generated `pnpm-lock.yaml`:

```json
{
  "name": "compliance-control-map-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest",
    "lint": "eslint . --max-warnings 0"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "1.1.15",
    "@tanstack/react-query": "5.101.2",
    "react": "19.2.0",
    "react-dom": "19.2.0",
    "react-router": "7.14.2"
  },
  "devDependencies": {
    "@eslint/js": "9.39.1",
    "@playwright/test": "1.58.2",
    "@testing-library/jest-dom": "6.9.1",
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.6.1",
    "@types/node": "24.10.1",
    "@types/react": "19.2.7",
    "@types/react-dom": "19.2.3",
    "@vitejs/plugin-react": "5.1.1",
    "eslint": "9.39.1",
    "eslint-plugin-react-hooks": "7.0.1",
    "eslint-plugin-react-refresh": "0.4.24",
    "globals": "16.5.0",
    "jsdom": "27.2.0",
    "typescript": "5.9.3",
    "typescript-eslint": "8.48.0",
    "vite": "7.3.6",
    "vitest": "4.0.15"
  },
  "packageManager": "pnpm@10.24.0"
}
```

```tsx
// frontend/src/App.tsx
export function App() {
  return <h1>Compliance Control Map</h1>;
}
```

Run from `frontend/`:

```powershell
corepack pnpm install
corepack pnpm test -- --run
corepack pnpm build
```

Expected: one frontend test passes and Vite production build exits 0.

- [ ] **Step 5: Commit the tested harness**

```powershell
git add backend frontend
git commit -m "build: establish tested application harness"
```

### Task 2: Add typed settings, database lifecycle, problem responses, and readiness health

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/middleware.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v1/health.py`
- Create: `backend/tests/core/test_config.py`
- Create: `backend/tests/core/test_errors.py`
- Create: `backend/tests/test_readiness.py`

- [ ] **Step 1: Write failing configuration and readiness tests**

```python
# backend/tests/core/test_config.py
from app.core.config import Settings


def test_local_defaults_are_loopback_and_sqlite(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, storage_root=tmp_path / "files")
    assert settings.bind_host == "127.0.0.1"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.auth_mode == "disabled"
```

```python
# backend/tests/test_readiness.py
def test_readiness_fails_when_database_is_unavailable(client_with_broken_db) -> None:
    response = client_with_broken_db.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
```

- [ ] **Step 2: Run the focused tests and verify missing settings/database modules fail**

```powershell
python -m pytest tests/core/test_config.py tests/test_readiness.py -q
```

Expected: import or fixture failure naming the missing core modules.

- [ ] **Step 3: Implement environment settings and the synchronous database manager**

```python
# backend/app/core/config.py
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CCM_", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    bind_host: str = "127.0.0.1"
    data_dir: Path = Path("/data")
    storage_root: Path = Path("/data/files")
    database_url: str = "sqlite:////data/compliance-control.db"
    auth_mode: Literal["disabled", "local"] = "disabled"
    allow_insecure_no_auth: bool = False
    allowed_origins: list[str] = Field(default_factory=list)
    max_upload_bytes: int = 50 * 1024 * 1024

    @model_validator(mode="after")
    def reject_remote_no_auth(self) -> "Settings":
        if self.auth_mode == "disabled" and self.bind_host not in {"127.0.0.1", "localhost"}:
            if not self.allow_insecure_no_auth:
                raise ValueError("disabled authentication may only bind to loopback")
        return self
```

Implement `DatabaseManager` with one SQLAlchemy engine, `pool_pre_ping=True`, SQLite foreign-key PRAGMA, session context manager with rollback, and `SELECT 1` readiness. Add request-ID and safe problem middleware; include request IDs in response headers and problem bodies.

- [ ] **Step 4: Run core tests and static checks**

```powershell
python -m pytest tests/core tests/test_readiness.py -q
python -m ruff check app tests
python -m mypy app
```

Expected: focused tests pass; Ruff and mypy report no errors.

- [ ] **Step 5: Commit core runtime behavior**

```powershell
git add backend/app/core backend/app/main.py backend/app/api/v1/health.py backend/tests
git commit -m "feat: add typed runtime and readiness checks"
```

### Task 3: Define the portable schema and first Alembic migration

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/catalog.py`
- Create: `backend/app/models/workspace.py`
- Create: `backend/app/models/assessment.py`
- Create: `backend/app/models/control.py`
- Create: `backend/app/models/library.py`
- Create: `backend/app/models/auth.py`
- Create: `backend/app/models/activity.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260821_0001_initial.py`
- Create: `backend/tests/models/test_schema.py`
- Create: `backend/tests/migrations/test_migrations.py`

- [ ] **Step 1: Write failing relationship and constraint tests**

```python
# backend/tests/models/test_schema.py
from sqlalchemy import inspect


def test_initial_schema_has_framework_control_crosswalk_and_library_tables(migrated_engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert {
        "frameworks", "framework_versions", "framework_domains", "framework_requirements",
        "workspaces", "requirement_assessments", "status_definitions", "organizational_controls",
        "requirement_control_mappings", "requirement_mappings", "documents", "evidence",
        "stored_files", "control_documents", "control_evidence", "requirement_documents",
        "requirement_evidence", "users", "sessions", "requirement_notes", "activity_events",
    } <= tables
```

Add tests that reject duplicate `(framework_version_id, external_id)`, duplicate assessment per workspace/requirement, self-crosswalks, and duplicate directed crosswalks.

- [ ] **Step 2: Run the schema tests and verify no migration exists**

```powershell
python -m pytest tests/models/test_schema.py tests/migrations/test_migrations.py -q
```

Expected: migration setup fails because the model metadata and revision are absent.

- [ ] **Step 3: Implement focused SQLAlchemy models and named constraints**

Use `Uuid(as_uuid=True)` with application-generated `uuid4`, timezone-aware timestamps, portable strings/integers/text, named foreign keys and unique/check constraints, and no PostgreSQL-only enum/array/JSONB behavior. `RequirementAssessment`, `OrganizationalControl`, `Document`, and `Evidence` carry `revision`. `ActivityEvent` uses portable JSON for safe snapshots. Every organizational table carries `workspace_id`.

The crosswalk constraint must be represented exactly:

```python
CheckConstraint("source_requirement_id <> target_requirement_id", name="ck_requirement_mapping_distinct"),
UniqueConstraint(
    "source_requirement_id",
    "target_requirement_id",
    "relationship_type",
    name="uq_requirement_mapping_direction_type",
),
```

Configure Alembic `render_as_batch=True` only for SQLite and import the complete metadata in `env.py`.

- [ ] **Step 4: Verify upgrade, downgrade, and a second upgrade**

```powershell
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m pytest tests/models/test_schema.py tests/migrations/test_migrations.py -q
```

Expected: all commands exit 0 and constraint tests pass.

- [ ] **Step 5: Commit the approved portable schema**

```powershell
git add backend/app/models backend/alembic.ini backend/alembic backend/tests/models backend/tests/migrations
git commit -m "feat: add portable compliance domain schema"
```

### Task 4: Validate and import framework packs, including the complete SOC 2 pack

**Files:**
- Create: `backend/app/frameworks/pack_schema.py`
- Create: `backend/app/frameworks/importer.py`
- Create: `backend/app/services/frameworks.py`
- Create: `backend/app/schemas/frameworks.py`
- Create: `backend/app/api/v1/frameworks.py`
- Create: `framework-packs/schema/framework-pack.schema.json`
- Create: `framework-packs/soc2/manifest.yaml`
- Create: `framework-packs/soc2/domains.yaml`
- Create: `framework-packs/soc2/requirements.yaml`
- Create: `framework-packs/soc2/README.md`
- Create: `backend/tests/frameworks/test_pack_validation.py`
- Create: `backend/tests/frameworks/test_importer.py`
- Create: `backend/tests/api/test_frameworks.py`

- [ ] **Step 1: Write failing full-pack and idempotency tests**

```python
# backend/tests/frameworks/test_pack_validation.py
from pathlib import Path

from app.frameworks.pack_schema import load_pack


def test_soc2_pack_contains_61_unique_requirements() -> None:
    pack = load_pack(Path("../framework-packs/soc2"))
    identifiers = [item.external_id for item in pack.requirements]
    assert len(identifiers) == 61
    assert len(set(identifiers)) == 61
    assert {"CC6.1", "A1.1", "PI1.1", "C1.1", "P8.1"} <= set(identifiers)
    assert pack.framework.version == "2017-tsc-pof-2022"
```

Add tests that every requirement references an existing domain/parent, summaries and guidance are different fields, import twice creates one version, and changed source hash with the same version is rejected.

- [ ] **Step 2: Run pack tests and verify the loader is missing**

```powershell
python -m pytest tests/frameworks -q
```

Expected: import failure for `app.frameworks.pack_schema`.

- [ ] **Step 3: Implement strict pack validation and transactional import**

Define Pydantic models with `extra="forbid"`. Normalize and hash the full canonical pack. Validate all references before opening the transaction. Insert Framework, immutable FrameworkVersion, domains, requirements, the singleton workspace, status definitions, and empty assessments. Do not update imported definition text in place.

Author all 61 concise summaries and separate illustrative guidance. Include the source URI, verified date, independent-summary disclaimer, and the exact identifier ranges approved in the design. Do not include official AICPA/COSO text, points of focus, PDFs, or logos.

- [ ] **Step 4: Verify pack tests and API output**

```powershell
python -m pytest tests/frameworks tests/api/test_frameworks.py -q
python -m app.frameworks.importer ../framework-packs/soc2
python -m app.frameworks.importer ../framework-packs/soc2
```

Expected: tests pass; both commands exit 0; the second reports the existing identical version without duplicate rows.

- [ ] **Step 5: Commit the immutable catalog vertical slice**

```powershell
git add backend/app/frameworks backend/app/services/frameworks.py backend/app/schemas/frameworks.py backend/app/api/v1/frameworks.py backend/tests framework-packs
git commit -m "feat: load complete SOC 2 framework pack"
```

---

## Phase 2 — Authenticated assessment, control, and evidence API

### Task 5: Add local identities, opaque sessions, CSRF, and role authorization

**Files:**
- Create: `backend/app/core/passwords.py`
- Create: `backend/app/core/sessions.py`
- Create: `backend/app/core/permissions.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/security/test_passwords.py`
- Create: `backend/tests/security/test_sessions.py`
- Create: `backend/tests/security/test_csrf.py`
- Create: `backend/tests/security/test_permissions.py`

- [ ] **Step 1: Write failing session and permission tests**

```python
def test_editor_can_update_but_viewer_cannot(editor_client, viewer_client, requirement_id) -> None:
    editor = editor_client.patch(
        f"/api/v1/requirements/{requirement_id}/assessment",
        headers={"X-CSRF-Token": editor_client.csrf},
        json={"status_code": "PARTIAL", "revision": 1},
    )
    viewer = viewer_client.patch(
        f"/api/v1/requirements/{requirement_id}/assessment",
        headers={"X-CSRF-Token": viewer_client.csrf},
        json={"status_code": "PARTIAL", "revision": 1},
    )
    assert editor.status_code != 403
    assert viewer.status_code == 403
```

Add tests for Argon2id hashes, 15-character minimum, 64-character acceptance, login session rotation, hash-only database storage, logout revocation, role-change revocation, missing/invalid CSRF, Origin rejection, generic login errors, dummy-hash missing user path, and source/account throttling.

- [ ] **Step 2: Run security tests and verify missing auth services fail**

```powershell
python -m pytest tests/security -q
```

Expected: imports or routes fail before auth implementation.

- [ ] **Step 3: Implement the session security boundary**

Generate 32 random bytes with `secrets.token_urlsafe(32)`, store only SHA-256 of the token, set `__Host-ccm_session` in TLS production and `ccm_session` for loopback development, and store a separate random CSRF secret server-side. Require `X-CSRF-Token` and a trusted Origin for every unsafe browser method, including login and upload. Centralize `require_role(Role.EDITOR)` and `require_role(Role.ADMIN)` dependencies.

In `AUTH_MODE=disabled`, inject a fixed system actor with Admin capabilities only after settings have enforced loopback or the explicit insecure override.

- [ ] **Step 4: Run all security tests and inspect cookie flags**

```powershell
python -m pytest tests/security -q
python -m ruff check app tests
```

Expected: all security tests pass; production cookie assertions include Secure, HttpOnly, SameSite=Lax, Path=/, and no Domain.

- [ ] **Step 5: Commit authentication and authorization**

```powershell
git add backend/app/core backend/app/services/auth.py backend/app/schemas/auth.py backend/app/api/v1 backend/tests/security
git commit -m "feat: secure local sessions and role authorization"
```

### Task 6: Implement assessments, notes, activity, filters, and concurrency

**Files:**
- Create: `backend/app/services/activity.py`
- Create: `backend/app/services/assessments.py`
- Create: `backend/app/schemas/requirements.py`
- Create: `backend/app/api/v1/requirements.py`
- Create: `backend/tests/services/test_assessments.py`
- Create: `backend/tests/api/test_requirements.py`
- Create: `backend/tests/api/test_requirement_notes.py`

- [ ] **Step 1: Write failing status, applicability, filtering, and revision tests**

```python
def test_not_applicable_status_and_applicability_remain_consistent(editor_client, requirement) -> None:
    response = editor_client.patch(
        f"/api/v1/requirements/{requirement.id}/assessment",
        headers={"X-CSRF-Token": editor_client.csrf},
        json={"status_code": "NOT_APPLICABLE", "revision": 1},
    )
    assert response.status_code == 200
    assessment = response.json()["data"]["assessment"]
    assert assessment["status_code"] == "NOT_APPLICABLE"
    assert assessment["applicability"] == "NOT_APPLICABLE"
```

Add tests for all CRUD fields, OR-within/AND-across filter semantics, search across ID/title/summary/tags, overdue filtering, note creation/editing, activity before/after snapshots, Viewer rejection, and stale revision returning `409` with current data.

- [ ] **Step 2: Run requirement tests and verify routes fail**

```powershell
python -m pytest tests/services/test_assessments.py tests/api/test_requirements.py tests/api/test_requirement_notes.py -q
```

Expected: route/service import failures.

- [ ] **Step 3: Implement transactions and response composition**

Keep routers thin. `AssessmentService.update()` loads the current row with its revision, applies field validation, synchronizes N/A status/applicability, increments revision, writes one safe ActivityEvent, commits, and returns a composed requirement/assessment representation. `list_requirements()` uses eager loading and aggregate subqueries to avoid per-row count queries.

Use this conflict contract:

```json
{
  "type": "https://compliance-control-map.local/problems/revision-conflict",
  "title": "The requirement changed before your update was saved",
  "status": 409,
  "detail": "Reload the current values and apply your change again.",
  "current": {"revision": 4}
}
```

- [ ] **Step 4: Run focused and query-count tests**

```powershell
python -m pytest tests/services/test_assessments.py tests/api/test_requirements.py tests/api/test_requirement_notes.py -q
```

Expected: all tests pass and the list query-count assertion remains constant when fixture rows increase.

- [ ] **Step 5: Commit the assessment workflow**

```powershell
git add backend/app/services backend/app/schemas/requirements.py backend/app/api/v1/requirements.py backend/tests
git commit -m "feat: assess and track framework requirements"
```

### Task 7: Implement organizational controls and cross-framework mappings

**Files:**
- Create: `backend/app/services/controls.py`
- Create: `backend/app/services/crosswalks.py`
- Create: `backend/app/schemas/controls.py`
- Create: `backend/app/schemas/crosswalks.py`
- Create: `backend/app/api/v1/controls.py`
- Create: `backend/app/api/v1/crosswalks.py`
- Create: `backend/tests/api/test_controls.py`
- Create: `backend/tests/api/test_crosswalks.py`

- [ ] **Step 1: Write failing many-to-many and no-status-transfer tests**

```python
def test_crosswalk_does_not_transfer_readiness(editor_client, ready_requirement, gap_requirement) -> None:
    response = editor_client.post(
        "/api/v1/requirement-mappings",
        headers={"X-CSRF-Token": editor_client.csrf},
        json={
            "source_requirement_id": str(ready_requirement.id),
            "target_requirement_id": str(gap_requirement.id),
            "relationship_type": "STRONG_OVERLAP",
            "confidence": 85,
            "mapping_source": "manual",
            "notes": "Shared access-control intent",
        },
    )
    assert response.status_code == 201
    refreshed = editor_client.get(f"/api/v1/requirements/{gap_requirement.id}").json()["data"]
    assert refreshed["assessment"]["status_code"] == "GAP"
```

Add tests for control CRUD, control status distinct from readiness, one control to multiple requirements, multiple controls to one requirement, rationale/coverage, crosswalk direction, self-link rejection, duplicate rejection, confidence range, provenance, and permissions.

- [ ] **Step 2: Run focused tests and verify missing endpoints fail**

```powershell
python -m pytest tests/api/test_controls.py tests/api/test_crosswalks.py -q
```

Expected: 404 or missing router failures.

- [ ] **Step 3: Implement control and crosswalk services with activity events**

Create `/controls`, `/controls/{id}`, `/requirements/{id}/controls`, `/requirement-mappings`, and `/requirements/{id}/mappings`. Validate relationship types against the approved four codes. Never call the assessment service from crosswalk creation. Emit activity for create, update, link, unlink, and crosswalk changes.

- [ ] **Step 4: Run control/crosswalk and assessment regression tests**

```powershell
python -m pytest tests/api/test_controls.py tests/api/test_crosswalks.py tests/services/test_assessments.py -q
```

Expected: all tests pass; readiness remains unchanged by mappings.

- [ ] **Step 5: Commit reusable controls and crosswalks**

```powershell
git add backend/app/services backend/app/schemas backend/app/api/v1 backend/tests/api
git commit -m "feat: map reusable controls and framework requirements"
```

### Task 8: Add secure file storage, document/evidence libraries, and reusable mappings

**Files:**
- Create: `backend/app/storage/base.py`
- Create: `backend/app/storage/local.py`
- Create: `backend/app/services/uploads.py`
- Create: `backend/app/services/documents.py`
- Create: `backend/app/services/evidence.py`
- Create: `backend/app/schemas/libraries.py`
- Create: `backend/app/api/v1/documents.py`
- Create: `backend/app/api/v1/evidence.py`
- Create: `backend/tests/storage/test_local_storage.py`
- Create: `backend/tests/security/test_uploads.py`
- Create: `backend/tests/api/test_documents.py`
- Create: `backend/tests/api/test_evidence.py`

- [ ] **Step 1: Write failing traversal, limit, random-key, and mapping tests**

```python
def test_upload_uses_random_storage_key_and_preserves_safe_metadata(editor_client, storage_root) -> None:
    response = editor_client.post(
        "/api/v1/documents",
        headers={"X-CSRF-Token": editor_client.csrf},
        data={"name": "Access Control Policy", "document_type": "POLICY"},
        files={"file": ("..\\Access Policy.txt", b"demo policy", "text/plain")},
    )
    assert response.status_code == 201
    stored = response.json()["data"]["file"]
    assert stored["original_filename"] == "Access Policy.txt"
    assert "Access Policy" not in stored["storage_key"]
    assert (storage_root / stored["storage_key"]).read_bytes() == b"demo policy"
```

Add tests for absolute/traversal/reserved filenames, unsupported extension, MIME mismatch, missing content length, streaming size cutoff, temporary cleanup, SHA-256, ZIP stored without unpacking, attachment/nosniff download, Viewer denial, map-once-to-many, unique direct/indirect counts, and no duplicate bytes when adding mappings.

- [ ] **Step 2: Run storage/upload/library tests and verify missing implementation fails**

```powershell
python -m pytest tests/storage tests/security/test_uploads.py tests/api/test_documents.py tests/api/test_evidence.py -q
```

Expected: import and route failures.

- [ ] **Step 3: Implement the streaming storage contract and library transactions**

```python
# backend/app/storage/base.py
from collections.abc import BinaryIO
from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    byte_size: int
    sha256: str
    detected_media_type: str


class FileStorage(Protocol):
    def put(self, stream: BinaryIO, *, extension: str, limit: int) -> StoredObject:
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError
```

`LocalFilesystemStorage.put()` must create a temp file inside the configured root, stream fixed-size chunks while hashing and enforcing the byte limit, validate the final resolved path remains inside the root, fsync, atomically rename to `<uuid><normalized-extension>`, and delete the temp file on every exception. Library creation cleans the stored object if the metadata transaction fails.

- [ ] **Step 4: Run security and mapping regressions**

```powershell
python -m pytest tests/storage tests/security tests/api/test_documents.py tests/api/test_evidence.py tests/api/test_controls.py -q
```

Expected: all tests pass; no orphan temp files remain.

- [ ] **Step 5: Commit secure reusable libraries**

```powershell
git add backend/app/storage backend/app/services backend/app/schemas/libraries.py backend/app/api/v1 backend/tests
git commit -m "feat: securely store and reuse compliance artifacts"
```

### Task 9: Add dashboard calculations, demo data, export, and empty-workspace restore

**Files:**
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/services/demo.py`
- Create: `backend/app/services/exports.py`
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/schemas/exports.py`
- Create: `backend/app/api/v1/dashboard.py`
- Create: `backend/app/api/v1/exports.py`
- Create: `backend/app/cli.py`
- Create: `backend/demo-files/demo-access-policy.txt`
- Create: `backend/demo-files/demo-quarterly-access-review.txt`
- Create: `backend/tests/services/test_dashboard.py`
- Create: `backend/tests/services/test_demo.py`
- Create: `backend/tests/services/test_exports.py`
- Create: `backend/tests/api/test_dashboard.py`

- [ ] **Step 1: Write failing readiness, demo, and export tests**

```python
def test_readiness_excludes_na_and_does_not_fractionally_credit_partial(dashboard_service, assessments) -> None:
    assessments.set("CC6.1", "READY")
    assessments.set("CC6.2", "PARTIAL")
    assessments.set("CC7.1", "GAP")
    assessments.set("P1.1", "NOT_APPLICABLE")
    result = dashboard_service.calculate()
    assert result.ready == 1
    assert result.denominator == 3
    assert result.readiness_percentage == 33
    assert result.assessed_percentage == 100
```

Add tests for zero denominator, all six counts, missing docs/evidence, overdue exclusion for N/A, gaps, recent activity, exact demo states, idempotent demo load, archive traversal rejection, hash verification, schema-version validation, secret/session exclusion, and restore refusal when workspace is populated.

- [ ] **Step 2: Run dashboard/export tests and verify missing services fail**

```powershell
python -m pytest tests/services/test_dashboard.py tests/services/test_demo.py tests/services/test_exports.py tests/api/test_dashboard.py -q
```

Expected: import failures for the missing services.

- [ ] **Step 3: Implement deterministic calculations and portable archives**

Use integer rounding with numerator/denominator included in the API so the percentage is explainable. Count unique direct-or-control-derived records. Export a ZIP with `manifest.json`, `workspace.json`, and content-addressed files under `files/<sha256>`; validate every member path and digest before restore. Exclude users' password hashes, sessions, CSRF secrets, runtime settings, and any future provider credentials.

Seed demo states exactly as approved and store only the two plainly labeled demo text files.

- [ ] **Step 4: Run dashboard, archive, and permission tests**

```powershell
python -m pytest tests/services/test_dashboard.py tests/services/test_demo.py tests/services/test_exports.py tests/api/test_dashboard.py tests/security/test_permissions.py -q
```

Expected: all tests pass; Viewer and Editor cannot create exports.

- [ ] **Step 5: Commit dashboard and portability services**

```powershell
git add backend/app backend/demo-files backend/tests
git commit -m "feat: calculate readiness and export portable workspaces"
```

---

## Phase 3 — Field Manual web application

### Task 10: Build the typed API client, session provider, router, and Field Manual shell

**Files:**
- Create: `frontend/src/app/api/types.ts`
- Create: `frontend/src/app/api/client.ts`
- Create: `frontend/src/app/query-client.ts`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/session/SessionProvider.tsx`
- Create: `frontend/src/app/layout/AppShell.tsx`
- Create: `frontend/src/app/layout/PrimaryNav.tsx`
- Create: `frontend/src/design/tokens.css`
- Create: `frontend/src/design/global.css`
- Create: `frontend/src/design/primitives/StatusMark.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/app/layout/AppShell.test.tsx`
- Create: `frontend/src/app/api/client.test.ts`

- [ ] **Step 1: Write failing navigation and CSRF-client tests**

```tsx
it("presents the six primary destinations in order", () => {
  renderApp("/dashboard");
  expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual([
    "Dashboard", "Framework Map", "Tracker", "Documents", "Evidence", "Settings",
  ]);
});
```

Add a client test that GET requests omit CSRF, unsafe requests fetch/cache `/auth/csrf` and include `X-CSRF-Token`, `409` responses become `RevisionConflict`, and `application/problem+json` details are preserved safely.

- [ ] **Step 2: Run focused frontend tests and verify missing providers fail**

```powershell
corepack pnpm test -- --run src/app
```

Expected: module resolution failures for router/client/shell.

- [ ] **Step 3: Implement generated-style types, API wrapper, and visual foundation**

Define one `ApiProblem`, `Envelope<T>`, session representation, framework-map representation, and mutation helper. Use same-origin `/api/v1`; do not hard-code hosts. Build the shell with CSS grid, shallow geometry, warm mineral paper, forest ink, rust accent, semantic status tokens, editorial heading stack, compact work typography, visible focus, skip link, and responsive navigation. Use SVG icons with accessible labels; do not use emoji as interface icons.

- [ ] **Step 4: Run component, accessibility, and build checks**

```powershell
corepack pnpm test -- --run src/app
corepack pnpm lint
corepack pnpm build
```

Expected: tests and build pass with no TypeScript errors.

- [ ] **Step 5: Commit the browser foundation**

```powershell
git add frontend
git commit -m "feat: establish Field Manual application shell"
```

### Task 11: Build generic framework filtering, tile navigation, and map view

**Files:**
- Create: `frontend/src/features/framework-map/types.ts`
- Create: `frontend/src/features/framework-map/api.ts`
- Create: `frontend/src/features/framework-map/filter-state.ts`
- Create: `frontend/src/features/framework-map/FrameworkFilters.tsx`
- Create: `frontend/src/features/framework-map/FrameworkMapPage.tsx`
- Create: `frontend/src/features/framework-map/FrameworkDomain.tsx`
- Create: `frontend/src/features/framework-map/RequirementTile.tsx`
- Create: `frontend/src/features/framework-map/useRovingDomainFocus.ts`
- Create: `frontend/src/features/framework-map/FrameworkMapPage.test.tsx`
- Create: `frontend/src/features/framework-map/RequirementTile.test.tsx`
- Create: `frontend/src/features/framework-map/useRovingDomainFocus.test.tsx`

- [ ] **Step 1: Write failing framework-agnostic map tests**

```tsx
it("renders injected domains, statuses, counts, and annotations without SOC 2 assumptions", async () => {
  server.use(frameworkMapFixture({ framework: "custom", externalId: "AC-1" }));
  renderApp("/frameworks/custom/map");
  expect(await screen.findByRole("button", {
    name: /AC-1.*Ready.*2 documents.*4 evidence/i,
  })).toBeVisible();
  expect(screen.queryByText(/SOC 2/i)).not.toBeInTheDocument();
});
```

Add tests for OR-within/AND-across filters, search, removable filters, result-count live region, parent disclosure, expand/collapse all, no-results copy, Arrow/Home/End navigation, focus persistence after filtering, and annotations rendered independently from status.

- [ ] **Step 2: Run map tests and verify missing components fail**

```powershell
corepack pnpm test -- --run src/features/framework-map
```

Expected: component import failures.

- [ ] **Step 3: Implement the atlas map**

Use generic `MapDomain`, `MapNode`, `AssessmentSummary`, `CountSummary`, and `MapAnnotation` types. Render domains as named layout grids with one roving tab stop, native buttons for tiles, identifier/status/count in accessible names, text/glyph/edge/color status redundancy, minimum 24px targets, and a contained horizontal canvas on desktop. At narrow widths stack domains without shrinking tile text.

Filter state is URL-serializable. Search input is debounced visually but preserves an immediate accessible label. Keep all SOC 2 copy in API data, never component constants.

- [ ] **Step 4: Run map, accessibility, and build checks**

```powershell
corepack pnpm test -- --run src/features/framework-map
corepack pnpm lint
corepack pnpm build
```

Expected: all map tests pass and production build exits 0.

- [ ] **Step 5: Commit the signature Framework Map**

```powershell
git add frontend/src/features/framework-map frontend/src/app/router.tsx
git commit -m "feat: add accessible framework atlas"
```

### Task 12: Add the responsive requirement detail sheet and core editing workflow

**Files:**
- Create: `frontend/src/features/framework-map/RequirementSheet.tsx`
- Create: `frontend/src/features/framework-map/tabs/OverviewTab.tsx`
- Create: `frontend/src/features/framework-map/tabs/ControlsTab.tsx`
- Create: `frontend/src/features/framework-map/tabs/DocumentsTab.tsx`
- Create: `frontend/src/features/framework-map/tabs/EvidenceTab.tsx`
- Create: `frontend/src/features/framework-map/tabs/ActivityTab.tsx`
- Create: `frontend/src/features/framework-map/RequirementForm.tsx`
- Create: `frontend/src/features/framework-map/RequirementSheet.test.tsx`
- Create: `frontend/src/features/framework-map/RequirementForm.test.tsx`

- [ ] **Step 1: Write failing focus, editing, and conflict tests**

```tsx
it("opens a modal sheet and restores focus to the originating tile", async () => {
  renderApp("/frameworks/soc2/map");
  const tile = await screen.findByRole("button", { name: /CC6.1/i });
  await user.click(tile);
  expect(screen.getByRole("dialog", { name: /CC6.1/i })).toBeVisible();
  await user.keyboard("{Escape}");
  expect(tile).toHaveFocus();
});
```

Add tests for 72–74% desktop class, 88% tablet class, full-screen phone class, focus containment, inactive background, all five tabs, status/applicability synchronization, owner/assignee/due/tags/notes, unsaved indicator, successful save, cancel, and 409 conflict reload choice.

- [ ] **Step 2: Run detail tests and verify missing sheet fails**

```powershell
corepack pnpm test -- --run src/features/framework-map/RequirementSheet.test.tsx src/features/framework-map/RequirementForm.test.tsx
```

Expected: missing component failures.

- [ ] **Step 3: Implement accessible modal-sheet editing**

Use an accessible dialog primitive for focus containment, Escape, inert background, close button, and focus restoration. Keep the map route active behind the sheet; represent the selected requirement in the URL so refresh/deep link works. Use explicit Save and Cancel, `aria-live` save status, native date fields, searchable people/tag controls, and safe textareas. On a conflict, show the current server revision and preserve the user's draft until they choose reload or copy.

Controls/Documents/Evidence tabs show direct and control-derived relationships separately and use searchable mapping dialogs. Activity interleaves user notes and system events with distinct labels.

- [ ] **Step 4: Run detail, map, and accessibility checks**

```powershell
corepack pnpm test -- --run src/features/framework-map
corepack pnpm lint
corepack pnpm build
```

Expected: all tests pass; no focus or TypeScript errors.

- [ ] **Step 5: Commit the assess-and-document interaction**

```powershell
git add frontend/src/features/framework-map frontend/src/app/router.tsx
git commit -m "feat: edit requirements in focused detail sheet"
```

### Task 13: Build Tracker, dashboard, document/evidence libraries, and Settings

**Files:**
- Create: `frontend/src/features/tracker/TrackerPage.tsx`
- Create: `frontend/src/features/tracker/AssessmentTable.tsx`
- Create: `frontend/src/features/tracker/InlineStatusSelect.tsx`
- Create: `frontend/src/features/dashboard/DashboardPage.tsx`
- Create: `frontend/src/features/dashboard/ReadinessLedger.tsx`
- Create: `frontend/src/features/dashboard/ActionQueues.tsx`
- Create: `frontend/src/features/libraries/LibraryPage.tsx`
- Create: `frontend/src/features/libraries/UploadDialog.tsx`
- Create: `frontend/src/features/libraries/LibraryDetail.tsx`
- Create: `frontend/src/features/settings/SettingsPage.tsx`
- Create: `frontend/src/features/settings/ExportPanel.tsx`
- Create: `frontend/src/features/settings/UsersPanel.tsx`
- Create: `frontend/src/features/tracker/AssessmentTable.test.tsx`
- Create: `frontend/src/features/dashboard/DashboardPage.test.tsx`
- Create: `frontend/src/features/libraries/UploadDialog.test.tsx`

- [ ] **Step 1: Write failing operational-view tests**

```tsx
it("explains readiness instead of implying fractional precision", async () => {
  renderApp("/dashboard");
  expect(await screen.findByText("33% ready")).toBeVisible();
  expect(screen.getByText("1 Ready ÷ 3 applicable requirements")).toBeVisible();
  expect(screen.getByText("100% assessed")).toBeVisible();
});
```

Add Tracker tests for native table headers, active `aria-sort`, sorting buttons, filters/search, inline status permissions, due dates/counts/last updated, horizontal small-screen wrapper, and Viewer read-only behavior. Add library tests for upload progress/errors, allowed-type help, metadata, multi-mapping, relationship inspection, attachment download, and duplicate-free counts. Add Settings tests for role-gated users/export and disabled inference copy.

- [ ] **Step 2: Run feature tests and verify missing pages fail**

```powershell
corepack pnpm test -- --run src/features/tracker src/features/dashboard src/features/libraries src/features/settings
```

Expected: missing page/component failures.

- [ ] **Step 3: Implement the operational views with the Field Manual visual language**

Use ledger strips, rules, and queues rather than generic metric-card grids. Tracker remains a native `<table>` with a caption and button-based sorting. Dashboard exposes numerator/denominator and assessed rate. Library upload uses multipart API calls and never previews untrusted files inline. Settings provides workspace information, users/roles, framework/source/disclaimer, export creation/download, and a clearly disabled future-inference section that stores no credentials.

Empty-state microcopy may be lightly playful; error, status, permission, export, and security copy remains literal.

- [ ] **Step 4: Run all frontend tests and build**

```powershell
corepack pnpm test -- --run
corepack pnpm lint
corepack pnpm build
```

Expected: complete frontend suite passes and production build exits 0.

- [ ] **Step 5: Commit the operational workspace**

```powershell
git add frontend/src/features frontend/src/app/router.tsx
git commit -m "feat: add tracker dashboard and artifact libraries"
```

---

## Phase 4 — Packaging, backup, hardening, and end-to-end verification

### Task 14: Add Docker images, Compose modes, launchers, and persistent startup

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker/nginx.conf`
- Create: `docker/entrypoint-api.sh`
- Create: `docker-compose.yml`
- Create: `docker-compose.server.yml`
- Create: `.env.example`
- Create: `launch.ps1`
- Create: `launch.sh`
- Create: `tests/ops/test-launch.ps1`
- Create: `tests/ops/test-compose.ps1`

- [ ] **Step 1: Write failing launcher and Compose contract tests**

```powershell
# tests/ops/test-launch.ps1
$script = Get-Content -Raw "$PSScriptRoot\..\..\launch.ps1"
if ($script -notmatch '\[switch\]\$Refresh') { throw 'Launcher must expose -Refresh' }
if ($script -notmatch '\[switch\]\$Yes') { throw 'Launcher must expose -Yes' }
if ($script -notmatch 'server mode cannot be refreshed') { throw 'Server refresh guard is missing' }
```

Add tests that Compose publishes only web port 3000, mounts named `ccm_sqlite_data` and `ccm_file_data` volumes, waits on migration completion/health, server overlay adds PostgreSQL and `AUTH_MODE=local`, secrets are environment-driven, and refresh names exact targets before confirmation.

- [ ] **Step 2: Run ops tests and verify files are missing**

```powershell
.\tests\ops\test-launch.ps1
.\tests\ops\test-compose.ps1
```

Expected: missing-file failures.

- [ ] **Step 3: Implement reproducible images, same-origin proxying, and safe launch behavior**

The API image installs locked dependencies, runs as a non-root user, and exposes no host port. The web image serves the Vite build and proxies `/api/v1` to `api:8000`, applies upload limits and security headers, and listens on container port 8080 mapped to host 3000.

`launch.ps1` and `launch.sh` implement `start`, `status`, local refresh, export, and empty-workspace restore. Default start copies `.env.example` only when `.env` is absent, runs Compose, waits for health with a bounded timeout, and prints the URL. Refresh resolves the Compose project name, verifies local SQLite mode, lists only `ccm_sqlite_data` and `ccm_file_data`, asks for explicit confirmation, and removes/recreates only those volumes. `-Yes`/`--yes` bypasses only that confirmation.

- [ ] **Step 4: Build images and prove restart persistence**

```powershell
.\tests\ops\test-launch.ps1
.\tests\ops\test-compose.ps1
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Create one assessment update and one demo text upload through the API, run `docker compose restart`, then GET both records and compare IDs/hashes. Expected: services become healthy and records survive restart.

- [ ] **Step 5: Commit deployment packaging**

```powershell
git add backend/Dockerfile frontend/Dockerfile docker docker-compose.yml docker-compose.server.yml .env.example launch.ps1 launch.sh tests/ops
git commit -m "feat: package persistent local and team deployments"
```

### Task 15: Add security headers, request limits, inference seam, project-agent guidance, and documentation

**Files:**
- Create: `backend/app/inference/base.py`
- Create: `backend/app/inference/models.py`
- Create: `backend/app/inference/README.md`
- Create: `agents/README.md`
- Create: `agents/schema/agent-profile.schema.json`
- Create: `skills/README.md`
- Create: `skills/schema/skill-manifest.schema.json`
- Create: `AGENTS.md`
- Create: `README.md`
- Create: `docs/security.md`
- Create: `docs/framework-packs.md`
- Create: `docs/backup-and-restore.md`
- Create: `backend/tests/inference/test_boundary.py`
- Create: `backend/tests/security/test_headers.py`

- [ ] **Step 1: Write failing security-header and disabled-inference tests**

```python
def test_security_headers_are_present(client) -> None:
    response = client.get("/api/v1/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_inference_gateway_is_not_registered_as_an_api_route(client) -> None:
    assert client.get("/api/v1/inference/providers").status_code == 404
```

Add interface tests that provider models contain base URL/IP, model ID, capability flags, timeout, TLS/data policies, and secret reference but cannot serialize a secret value. Confirm no backend production module imports an OpenAI/provider SDK.

- [ ] **Step 2: Run boundary/security tests and verify missing modules fail**

```powershell
python -m pytest tests/inference/test_boundary.py tests/security/test_headers.py -q
```

Expected: missing interface/header failures.

- [ ] **Step 3: Implement disabled protocols and operator documentation**

```python
# backend/app/inference/base.py
from collections.abc import AsyncIterator
from typing import Protocol

from app.inference.models import InferenceRequest, InferenceEvent, ProviderCapabilities


class InferenceGateway(Protocol):
    @property
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    def stream(self, request: InferenceRequest) -> AsyncIterator[InferenceEvent]:
        raise NotImplementedError
```

Define serializable, provider-neutral request/event models with scoped record references and tool/skill identifiers, but no working implementation, route, credential persistence, or provider SDK. JSON Schemas document future `agent.yaml` and skill manifests. `AGENTS.md` enforces framework-agnostic domain logic, TDD, upload safety, no AI runtime in V1, no GitHub remote changes, and full verification commands.

README quick start begins with `./launch` commands before developer detail and documents architecture, both deployment modes, configuration, persistence, safe refresh, export/restore, database switching, framework packs, tests, security, SOC 2 disclaimer, and future architecture.

- [ ] **Step 4: Run security/boundary tests and documentation link checks**

```powershell
python -m pytest tests/inference/test_boundary.py tests/security/test_headers.py -q
python -m ruff check app tests
```

Expected: tests pass, no provider SDK import exists, and all documented local file links resolve.

- [ ] **Step 5: Commit hardening and handoff documentation**

```powershell
git add backend/app/inference backend/tests agents skills AGENTS.md README.md docs
git commit -m "docs: harden and document the self-hosted workspace"
```

### Task 16: Add end-to-end acceptance coverage and verify both databases

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/mvp-workflow.spec.ts`
- Create: `frontend/e2e/permissions.spec.ts`
- Create: `frontend/e2e/accessibility.spec.ts`
- Create: `tests/smoke/local-mode.ps1`
- Create: `tests/smoke/server-mode.ps1`
- Modify: `backend/tests/conftest.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing browser acceptance workflow**

```ts
test("assess, control, document, evidence, track, export, and persist", async ({ page }) => {
  await page.goto("/frameworks/soc2/map");
  await page.getByRole("button", { name: /CC6.1/i }).click();
  await page.getByLabel("Readiness").selectOption("READY");
  await page.getByLabel("Implementation notes").fill("Access is approved, reviewed, and revoked.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved")).toBeVisible();
  await page.getByRole("tab", { name: /Controls/ }).click();
  await page.getByRole("button", { name: "Create control" }).click();
  await page.getByLabel("Control name").fill("Access lifecycle management");
  await page.getByRole("button", { name: "Save control" }).click();
  await page.getByRole("link", { name: "Documents" }).click();
  await page.getByRole("button", { name: "Upload document" }).click();
  await page.getByLabel("Name").fill("Demo Access Policy");
  await page.getByLabel("File").setInputFiles("../backend/demo-files/demo-access-policy.txt");
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("Demo Access Policy")).toBeVisible();
});
```

Extend the test to map that document and an evidence record to multiple requirements/controls, inspect both sides, search/filter the map, use Tracker inline status, validate dashboard numerator/denominator, create/download export, restart containers through the smoke harness, and confirm records persist.

- [ ] **Step 2: Run E2E against local Compose and verify the test exposes missing integration details**

```powershell
corepack pnpm exec playwright install chromium
.\launch.ps1 -Refresh -Yes
corepack pnpm exec playwright test e2e/mvp-workflow.spec.ts
```

Expected before final fixes: at least one concrete failing selector, API contract, seed, or integration behavior; capture the first failure and fix only the product behavior.

- [ ] **Step 3: Complete browser permission, accessibility, and server-mode coverage**

Permissions test logs in as Viewer/Editor/Admin and proves route/action boundaries. Accessibility test covers skip navigation, map arrow keys, tile accessible names, modal focus/restore, filter live region, table sorting semantics, status not color-only, and 200% zoom/reflow screenshots. Server smoke starts the PostgreSQL overlay, runs Alembic, executes the complete backend API suite against PostgreSQL, and performs a document upload/download round trip.

- [ ] **Step 4: Run the fresh full verification matrix**

```powershell
python -m pytest backend/tests -q
python -m ruff check backend/app backend/tests
python -m mypy backend/app
corepack pnpm --dir frontend test -- --run
corepack pnpm --dir frontend lint
corepack pnpm --dir frontend build
docker compose config --quiet
.\tests\smoke\local-mode.ps1
.\tests\smoke\server-mode.ps1
corepack pnpm --dir frontend exec playwright test
```

Expected: every command exits 0; pytest/Vitest/Playwright report zero failures; both database smoke tests and restart persistence pass.

- [ ] **Step 5: Commit acceptance evidence and final local handoff**

```powershell
git add frontend/e2e frontend/playwright.config.ts tests README.md
git commit -m "test: verify complete compliance workspace workflow"
git status --short
```

Expected: clean feature worktree. Do not push or configure a remote.

---

## Final requirement trace

| Design requirement | Implementing tasks |
|---|---|
| SQLite/PostgreSQL single codebase and migrations | 2, 3, 14, 16 |
| Generic versioned frameworks and complete SOC 2 pack | 3, 4 |
| Requirement assessments, ownership, dates, notes, tags | 6, 12 |
| Lightweight organizational controls | 3, 7, 12 |
| Cross-framework mapping API without status transfer | 3, 7 |
| Secure document/evidence reuse and mappings | 8, 12, 13 |
| Readiness/dashboard calculations | 9, 13 |
| Framework Map, filters, accessibility, detail sheet | 11, 12 |
| Tracker and inline updates | 13 |
| Sessions, roles, CSRF, authorization | 5, 10, 13 |
| Export and empty-workspace restore | 9, 13, 14 |
| One-command launch, safe refresh, persistence | 14, 16 |
| Field Manual design and restrained humor | 10–13 |
| Disabled provider-neutral inference seam | 15 |
| Security hardening and operator documentation | 5, 8, 14, 15 |
| Full local/team/browser verification | 16 |
