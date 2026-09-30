# Internal Deployment and User Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superjawn:subagent-driven-development (recommended) or superjawn:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship safe Admin account lifecycle controls, self-service password changes, a small access-change ledger, and a clear local-demo-to-internal-deployment handoff.

**Architecture:** Extend the existing single-workspace `/users` and `/auth` boundaries without a schema migration. Reuse `ActivityEvent` for audit records, existing server-side session revocation, and the Settings page for a compact administration UI. Keep local no-auth mode unchanged and make server bootstrap secrets removable after first login.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Argon2id, React, TypeScript, TanStack Query, Vitest, Playwright, PowerShell, Docker Compose.

---

### Task 1: User lifecycle API and activity ledger

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/v1/users.py`
- Modify: `backend/tests/security/test_auth_api.py`

- [ ] **Step 1: Write failing lifecycle tests**

Add tests that create a second Admin, assert `GET /users` exposes `is_disabled`, deactivate/reactivate a Viewer, change its role and password, verify its session is revoked, reject self-demotion/deactivation, reject removing the final active Admin, delete the Viewer, and confirm `USER_DELETED` remains in `activity_events` with no password value.

```python
def test_admin_lifecycle_is_guarded_audited_and_revokes_sessions(auth_app):
    client, manager, admin_id, viewer_id = auth_app
    _login(client, "viewer@example.com", "a sturdy viewer passphrase")
    viewer_cookie = client.cookies.get("ccm_session")
    assert viewer_cookie is not None
    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": str(admin_session["csrf_token"])}

    blocked = client.patch(f"/api/v1/users/{admin_id}", headers=headers, json={"is_disabled": True})
    assert blocked.status_code == 409

    changed = client.patch(
        f"/api/v1/users/{viewer_id}",
        headers=headers,
        json={"role": "EDITOR", "is_disabled": True, "password": "a replacement viewer passphrase"},
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["is_disabled"] is True

    client.cookies.set("ccm_session", viewer_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    admin_session = _login(client, "admin@example.com", "a sturdy admin passphrase")
    headers["X-CSRF-Token"] = str(admin_session["csrf_token"])
    deleted = client.delete(f"/api/v1/users/{viewer_id}", headers=headers)
    assert deleted.status_code == 204

    activity = client.get("/api/v1/users/activity").json()["data"]
    deletion = next(item for item in activity if item["action_code"] == "USER_DELETED")
    assert deletion["before"]["email"] == "viewer@example.com"
    assert "password" not in str(deletion).casefold()
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `cd backend; python -m pytest tests/security/test_auth_api.py -q`

Expected: failures because account state, password updates, deletion, safety conflicts, and `/users/activity` are not implemented.

- [ ] **Step 3: Implement lifecycle behavior**

Extend response/update schemas:

```python
class UserResponse(APIModel):
    id: UUID
    email: str | None
    display_name: str
    role: Role
    is_disabled: bool


class UserUpdate(APIModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Role | None = None
    is_disabled: bool | None = None
    password: str | None = Field(default=None, min_length=15, max_length=128)
```

In `users.py`, add snapshot/activity helpers, active-Admin counting, self/final-Admin guards, password hashing with session revocation, `DELETE /{user_id}`, and `GET /activity`. Record actions through `record_activity`; never include `password` or `password_hash` in a snapshot. Declare `/activity` before `/{user_id}` routes.

```python
def _snapshot(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_disabled": user.is_disabled,
    }


def _protect_current_admin(user: User, principal: Principal, payload: UserUpdate) -> None:
    removes_access = payload.is_disabled is True or (
        payload.role is not None and payload.role is not Role.ADMIN
    )
    if user.id == principal.user_id and removes_access:
        raise HTTPException(status_code=409, detail="You cannot remove your own administrator access.")
```

- [ ] **Step 4: Run lifecycle tests and full backend checks**

Run: `cd backend; python -m pytest tests/security/test_auth_api.py -q; python -m ruff check app tests; python -m mypy app`

Expected: focused tests pass; Ruff and mypy report no errors.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/app/schemas/auth.py backend/app/api/v1/users.py backend/tests/security/test_auth_api.py
git commit -m "feat: add audited user lifecycle controls"
```

### Task 2: Self-service password change

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/v1/auth.py`
- Modify: `backend/tests/security/test_auth_api.py`

- [ ] **Step 1: Write the failing password-change test**

```python
def test_user_changes_password_with_current_password_and_all_sessions_are_revoked(auth_app):
    client, _manager, _admin_id, _viewer_id = auth_app
    session = _login(client, "viewer@example.com", "a sturdy viewer passphrase")
    wrong = client.post(
        "/api/v1/auth/change-password",
        headers={"Origin": ORIGIN, "X-CSRF-Token": str(session["csrf_token"])},
        json={"current_password": "not the current password", "new_password": "a replacement viewer passphrase"},
    )
    assert wrong.status_code == 401
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Origin": ORIGIN, "X-CSRF-Token": str(session["csrf_token"])},
        json={"current_password": "a sturdy viewer passphrase", "new_password": "a replacement viewer passphrase"},
    )
    assert changed.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    _login(client, "viewer@example.com", "a replacement viewer passphrase")
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd backend; python -m pytest tests/security/test_auth_api.py::test_user_changes_password_with_current_password_and_all_sessions_are_revoked -q`

Expected: 404 because `/auth/change-password` does not exist.

- [ ] **Step 3: Implement the endpoint**

Add a Pydantic request with both fields limited to 128 characters. Load the current user by `principal.user_id`, verify the current password, hash the replacement, record `PASSWORD_CHANGED` with no secret snapshot, revoke all user sessions, clear session/CSRF cookies, and return 204.

```python
class PasswordChangeRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=128)
```

- [ ] **Step 4: Run auth tests and backend checks**

Run: `cd backend; python -m pytest tests/security/test_auth_api.py -q; python -m ruff check app tests; python -m mypy app`

Expected: all pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/app/schemas/auth.py backend/app/api/v1/auth.py backend/tests/security/test_auth_api.py
git commit -m "feat: add self-service password changes"
```

### Task 3: Compact Settings user administration

**Files:**
- Modify: `frontend/src/features/settings/UsersPanel.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.test.tsx`
- Modify: `frontend/src/features/operations.css`

- [ ] **Step 1: Write failing component tests**

Mock `/users` with one active Admin and one deactivated Viewer. Assert state labels and Edit, Reactivate, Reset password, and Delete actions. Submit a role change, verify PATCH payload, confirm a delete dialog, verify DELETE, and submit `/auth/change-password` with current/new values. Assert dialogs have accessible names and errors use `role="alert"`.

```tsx
expect(await screen.findByText("Deactivated")).toBeVisible();
await user.click(screen.getByRole("button", { name: "Edit Evidence Viewer" }));
await user.selectOptions(screen.getByLabelText("Role"), "EDITOR");
await user.click(screen.getByRole("button", { name: "Save user" }));
expect(api.patch).toHaveBeenCalledWith("/users/viewer", expect.objectContaining({ role: "EDITOR" }));
```

- [ ] **Step 2: Run the Settings test and confirm RED**

Run: `cd frontend; corepack pnpm test --run src/features/settings/SettingsPage.test.tsx`

Expected: missing account state/actions and password form assertions fail.

- [ ] **Step 3: Implement the Settings experience**

Refactor `UsersPanel` into focused internal components in the same file: user row, edit/reset dialog, delete dialog, add form, account activity, and self password form. Use native `<dialog>` through the project's existing dialog pattern, explicit labels, `aria-live`/`role="alert"`, and named buttons. Invalidate `users` and `user-activity` queries after mutations. On successful self password change, clear the session user and navigate to `/login`.

Use this record shape:

```ts
interface UserRecord {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  is_disabled: boolean;
}
```

- [ ] **Step 4: Run frontend checks**

Run: `cd frontend; corepack pnpm test --run; corepack pnpm lint; corepack pnpm build`

Expected: unit tests, lint, and production build pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add frontend/src/features/settings/UsersPanel.tsx frontend/src/features/settings/SettingsPage.tsx frontend/src/features/settings/SettingsPage.test.tsx frontend/src/features/operations.css
git commit -m "feat: add settings user administration"
```

### Task 4: Credentials and demo-to-deployment handoff

**Files:**
- Modify: `docker-compose.server.yml`
- Modify: `launch.ps1`
- Modify: `launch.sh`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `tests/ops/test-compose.ps1`
- Modify: `tests/ops/test-launch.ps1`
- Modify: `tests/ops/test-docs.ps1`

- [ ] **Step 1: Write failing contract tests**

Add assertions that the server bootstrap password can be blank after initialization, the launcher contains server placeholder preflight and login-email output without password output, and README explicitly documents Local credentials, Server credentials, Fresh internal deployment, and Promote genuine local work.

```powershell
if ($readme -notmatch 'Local mode: no login') { throw 'Local credentials are not explicit' }
if ($readme -notmatch 'CCM_BOOTSTRAP_ADMIN_EMAIL') { throw 'Server login email is not documented' }
if ($readme -notmatch 'Promote genuine local work') { throw 'Promotion path is not documented' }
if ($launcher -match 'Write-Host.+BOOTSTRAP_ADMIN_PASSWORD') { throw 'Launcher must not print the password' }
```

- [ ] **Step 2: Run ops tests and confirm RED**

Run: `./tests/ops/test-compose.ps1; ./tests/ops/test-launch.ps1; ./tests/ops/test-docs.ps1`

Expected: new documentation and launcher assertions fail.

- [ ] **Step 3: Implement preflight and documentation**

Make the server overlay pass empty bootstrap values after initial setup:

```yaml
CCM_BOOTSTRAP_ADMIN_EMAIL: ${CCM_BOOTSTRAP_ADMIN_EMAIL:-}
CCM_BOOTSTRAP_ADMIN_PASSWORD: ${CCM_BOOTSTRAP_ADMIN_PASSWORD:-}
```

In both launchers, validate server-start `.env` values before Compose: reject `CHANGE_ME`, require PostgreSQL password and allowed origins/hosts, and require bootstrap email/password only when the operator has not intentionally cleared them after initialization. After ready, print `Login email: <configured email>` and `Initial password: see CCM_BOOTSTRAP_ADMIN_PASSWORD in .env` without printing its value.

Document exact credentials, first login, password change, clearing the bootstrap secret, no-demo server startup, TLS, backup, fresh deployment, and local export/empty-server restore.

- [ ] **Step 4: Run ops/Compose checks**

Run: `./tests/ops/test-compose.ps1; ./tests/ops/test-launch.ps1; ./tests/ops/test-docs.ps1; docker compose config --quiet`

Expected: all pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docker-compose.server.yml launch.ps1 launch.sh .env.example README.md tests/ops
git commit -m "docs: add internal deployment handoff"
```

### Task 5: Browser acceptance and final verification

**Files:**
- Modify: `frontend/e2e/permissions.spec.ts`
- Modify: `tests/smoke/server-mode.ps1`

- [ ] **Step 1: Extend the failing server browser workflow**

Add an Admin scenario that creates a user, edits its role, deactivates/reactivates it, resets its password, verifies recent activity, and deletes it. Retain Viewer/Editor permission checks.

- [ ] **Step 2: Run the focused server smoke**

Run: `./tests/smoke/server-mode.ps1`

Expected: PostgreSQL API tests and Admin/Editor/Viewer browser workflows pass.

- [ ] **Step 3: Run complete verification**

Run backend tests, Ruff, mypy, frontend unit tests, lint, production build, Playwright accessibility/workflow tests, local smoke, server smoke, Compose contracts, dependency audit, `git diff --check`, and a clean health request.

Expected: all checks pass; server PostgreSQL suite retains only the intentional SQLite-only skip.

- [ ] **Step 4: Commit Task 5**

```powershell
git add frontend/e2e/permissions.spec.ts tests/smoke/server-mode.ps1
git commit -m "test: verify internal user administration"
```
