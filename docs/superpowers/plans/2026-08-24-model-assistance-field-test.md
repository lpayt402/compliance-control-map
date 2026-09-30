# Model Assistance Field-Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `executing-plans` and `test-driven-development`. The approved field-test prompt requires the main agent to own all implementation; subagents are read-only reconnaissance only. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver optional, default-off, secure, contextual model assistance and the specified field-test polish without changing the compliance product boundary.

**Architecture:** Add workspace-scoped provider/run persistence and a bounded single-agent runtime behind `InferenceGateway`. Context, authorization, tools, output validation, streaming, and terminal persistence remain application-owned; provider/framework details stay isolated under `backend/app/inference/`.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Pydantic, conditional `pydantic-ai-slim[openai]`, React/TypeScript, TanStack Query, Vitest, Playwright, Docker Compose, Nginx NDJSON streaming.

---

### Task 1: Lock the optional boundary and restore a trustworthy Docker baseline

**Files:** `AGENTS.md`, new `.gitattributes`, `tests/ops/test-launch.ps1`, `docker/entrypoint-api.sh`

- [ ] Add a failing ops assertion that Linux shell entrypoints are checked out with LF and run it to reproduce the current CRLF failure.
- [ ] Add the smallest Git text rule, re-check the worktree file, and rerun local/server smoke startup.
- [ ] Preserve `CCM_INFERENCE_ENABLED=false` as the documented and tested default.

### Task 2: Prove or reject the preferred runtime before broad implementation

**Files:** `backend/pyproject.toml`, `backend/tests/inference/test_runtime_spike.py`, `backend/app/inference/openai_compatible.py`

- [ ] Write a failing deterministic structured-proposal test and a failing fake Chat Completions SSE/tool-call test.
- [ ] Exact-pin `pydantic-ai-slim[openai]==2.33.0` and only the required compatible transitive boundaries; keep tracing disabled.
- [ ] Implement the narrow adapter proof inside `app/inference/`; run pytest, Ruff, and mypy.
- [ ] If either proof cannot pass without leaking framework types or weakening typing/bounds, remove the dependency and implement the same loop with the existing HTTP client stack.

### Task 3: Add configuration, destination, secret, and manifest fail-closed foundations

**Files:** `backend/app/core/config.py`, `backend/app/inference/provider_security.py`, `backend/app/inference/registry.py`, agent/skill schemas and built-ins, focused inference/core tests

- [ ] Add failing tests for default-off settings, safe bounds, exact URL normalization, policy/DNS/redirect/proxy blocks, `env:`-only secrets, and sanitized errors.
- [ ] Add failing loader tests for invalid schema, duplicates, traversal, absolute paths, symlink escape, undeclared tools/scopes, writes, disabled entries, and excessive limits.
- [ ] Implement minimal settings, destination policy, request-time secret resolver, registry, one agent profile, and four versioned skills.

### Task 4: Add the additive data/API/authorization boundary

**Files:** new `backend/app/models/inference.py`, migration `20260824_0003`, inference schemas/service/router, model/main exports, migration/API/privacy tests

- [ ] Write failing SQLite/PostgreSQL-capable migration/model tests for workspace-scoped profiles, one default, revisions, nullable local actor, run terminal fields, feedback, and profile-delete snapshots.
- [ ] Write failing Admin/Editor/Viewer, CSRF, cross-workspace, stale-revision, secret-rejection, and export-exclusion tests.
- [ ] Implement provider/status/skills/history/detail/feedback endpoints and sanitized activity using existing envelope/problem/role/workspace patterns.
- [ ] Keep disabled run/test paths fail-closed without constructing a provider client or making network calls.

### Task 5: Build authorized context, tools, and the bounded runtime

**Files:** `backend/app/inference/context.py`, `tools.py`, `runtime.py`, `base.py`, `models.py`, focused context/tool/runtime tests

- [ ] Write failing tests proving selected-record scope, no storage open/download, prompt text remains data, deterministic budget/omissions/digest, source validation, and confirmation invalidation.
- [ ] Write failing tests for tool registry intersection, Pydantic arguments, repeated principal/workspace/object authorization, bounded results, and rejected attempts counting toward limits.
- [ ] Write failing tests for no-tools/no-structure fallback, bounded repair, four turns/eight calls, output/response limits, atomic admission, cancellation/disconnect/timeout, stale-run recovery, usage, and exactly one terminal state.
- [ ] Implement the smallest context builder, read-only tools, admission controller, and NDJSON runtime that make those tests pass.

### Task 6: Add provider management and contextual assistance UI

**Files:** frontend API types/client; new `features/settings/ModelAssistanceSettings.tsx`; new `features/inference/AssistancePanel.tsx`; Settings/RequirementSheet/ControlDetail/EntityResources and tests

- [ ] Write failing streaming-client tests for CSRF, fragmented lines, abort, malformed input, unexpected EOF, and terminal enforcement.
- [ ] Write failing provider-panel tests for disabled/unconfigured/ready, secret status only, policy errors, visible test progress/outcome, and Admin-only behavior.
- [ ] Write failing assistance-panel tests for minimal context defaults, preview/omissions, per-run external confirmation, finite states, structured/unstructured output, sources, cancellation/timeout/errors, and feedback.
- [ ] Write failing detail/resource tests proving draft callbacks change local state only, protect unsaved text, never change statuses, and wait for the existing normal Save request.
- [ ] Implement accessible components with explicit Admin/Editor predicates, polite phase announcements, terminal alerts, named source lists/fieldsets, focus management, and 44px primary targets.

### Task 7: Complete the bounded polish items

**Files:** shared frontend formatter/activity helpers; EntityResources, RequirementSheet, ControlDetail, LibraryDetail, Settings/users components and tests

- [ ] Reproduce date-only timezone shift, owner fallback, silent mutation errors, and unreadable activity with failing tests.
- [ ] Add one date-only formatter, actual owner display, visible mutation/provider-test errors, action labels, actor display names, and safe changed-field summaries.
- [ ] Do not add unrelated visual or workflow polish.

### Task 8: Package, proxy, document, and prove the field workflow

**Files:** Dockerfiles, Compose, Nginx, `.env.example`, README/security/backup docs, new model-assistance/checklist docs, ops/smoke/Playwright tests

- [ ] Add failing contracts for copied agent/skill roots, host-gateway mapping, default-off environment, no provider port, and unbuffered inference streaming.
- [ ] Update images/networking/proxy while preserving existing headers and supporting same-network, Docker-host, and explicit HTTPS providers.
- [ ] Add the deterministic fake-provider browser workflow for Admin setup/test, Editor requirement/control drafts, manual saves, cancellation/timeout, Viewer denial, overflow, and backup privacy.
- [ ] Document setup, exact allowlist/env secret behavior, context/exclusions, external transfer, roles/limits, kill switch, troubleshooting, known limits, no-audit disclaimer, and the concise field checklist.

### Task 9: Verify in at most three implementation/validation cycles

**Files:** all changed files and validation evidence

- [ ] Cycle 1: focused backend proofs/security/migration tests, then backend pytest/Ruff/mypy/Alembic.
- [ ] Cycle 2: focused frontend/client/component/accessibility tests, then frontend tests/lint/build/Playwright.
- [ ] Cycle 3: ops/Compose, local SQLite smoke, PostgreSQL server smoke, packaged browser workflow, fake provider, and Docker-to-host connectivity where the environment permits.
- [ ] Record exact totals and concrete blockers for real Ollama/hosted credentials; never claim an unrun test passed.
- [ ] Review the diff for out-of-scope work, secret/raw-payload leakage, automatic writes, attachment-byte access, and any P0/P1 defect before declaring field-test readiness.
