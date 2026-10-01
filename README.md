# Compliance Control Map

A self-hosted workspace for SOC 2 readiness. Map requirements, assign gaps, and link controls, documents, and evidence. The map view gives each requirement a compact detail panel.

SOC 2 Trust Services Criteria is the first included framework. Requirements and organizational controls stay separate, so one control can support multiple frameworks while their statuses remain distinct.

## Quick start

You need Docker Desktop (Windows/macOS) or Docker Engine with Compose (Linux). From this folder, run one command:

```powershell
.\launch.ps1
```

On macOS or Linux:

```sh
./launch.sh
```

The first run creates `.env` from safe local defaults, builds the containers, loads the SOC 2 pack and clearly labeled demo records, and prints:

```text
Ready: http://localhost:3000
```

Open [http://localhost:3000](http://localhost:3000). Local mode binds only to this computer and does not require a login.

Useful commands:

```powershell
.\launch.ps1 -Mode status
.\launch.ps1 -Mode down
.\launch.ps1 -Mode export -Archive data\my-backup.zip
.\launch.ps1 -Refresh
```

`-Refresh` is for local testing. It shows the two exact project volumes and requires typing `REFRESH` before it deletes and recreates them. `-Refresh -Yes` skips the confirmation; use it only when you intend to discard the local workspace. Server mode refuses refresh.

## Credentials

**Local mode: no login and no credentials.** It is intentionally limited to `127.0.0.1` and is suitable for solo work and demo/testing.

**Server mode:** the first login email is the value of `CCM_BOOTSTRAP_ADMIN_EMAIL` in `.env`; the first password is `CCM_BOOTSTRAP_ADMIN_PASSWORD`. The launcher prints the email but never prints the password. These are bootstrap credentials, not built-in defaults—replace the example values before the first server start.

After signing in, open **Settings → Change my password**. A successful change signs that account out everywhere. Confirm the new password works, then clear both bootstrap values in `.env`:

```dotenv
CCM_BOOTSTRAP_ADMIN_EMAIL=
CCM_BOOTSTRAP_ADMIN_PASSWORD=
```

Later restarts use the Admin stored in PostgreSQL. A fresh database with blank bootstrap values fails closed with a clear error.

Admins manage accounts under **Settings → Users and roles**. They can add users, edit roles, deactivate/reactivate access, reset passwords, and permanently delete edge-case accounts. Deactivation is the normal offboarding choice. The compact access ledger records these actions; it is useful operational history, not an immutable system-of-record audit log.

## What is included

- Dashboard with status counts, honest readiness math, gaps, overdue work, missing documentation/evidence, and recent changes.
- Framework Map with status colors plus text labels, filtering, search, keyboard access, and a modal detail sheet.
- Tracker with sorting, filtering, search, and inline readiness changes.
- Requirement ownership, assignee, due date, applicability, tags, implementation notes, typed notes/playbooks/contacts, and activity.
- Reusable document and evidence libraries with many-to-many mappings.
- Organizational controls that can support many requirements and carry shared documents/evidence.
- Generic requirement crosswalk records with typed, non-transitive overlap relationships.
- Local SQLite/filesystem mode and PostgreSQL team mode from the same API and frontend.
- Structured ZIP export and empty-workspace restore.
- Admin, Editor, and Viewer roles in team mode.
- Optional, default-off model assistance with exact context review, bounded read-only tools, streamed advisory output, and human-saved local drafts.

Readiness is the whole-number percentage `READY / (ALL - NOT_APPLICABLE)`. A partial or in-progress item is not counted as ready. This avoids invented fractional certainty; assessed coverage is shown separately.

## Architecture

```text
Browser → Nginx/Vite frontend → FastAPI REST API
                                  ├─ SQLite or PostgreSQL
                                  └─ LocalFilesystemStorage

Framework → Requirement ← Crosswalk → Requirement
                    ↕
          Organizational Control
               ↙          ↘
          Documents      Evidence
```

The browser always uses `/api/v1`, including in local mode. Framework catalogs, workspace assessments, control operation, and file coverage are separate concerns. The local storage interface can later gain an S3-compatible adapter without changing API consumers.

Primary API groups are `/frameworks`, `/requirements`, `/controls`, `/crosswalks`, `/documents`, `/evidence`, `/users`, `/dashboard`, `/exports`, `/auth`, and the optional `/inference` boundary. Interactive OpenAPI documentation is served by FastAPI at `/docs` on the API origin; the packaged frontend intentionally proxies only `/api/`.

## Team/server mode

### Set up a server workspace

1. Run the local launcher once to create `.env`, then replace every `CHANGE_ME` value and both `example.com` entries.
2. Use a unique 15+ character Admin passphrase and a separate long, random PostgreSQL password.
3. Set `CCM_ALLOWED_ORIGINS` to the exact browser-facing HTTPS origin and `CCM_ALLOWED_HOSTS` to the deployed hostname. Keep `CCM_SERVER_LOAD_DEMO=false`.
4. Start team mode:

```powershell
.\launch.ps1 -Deployment server
```

   On macOS/Linux: `./launch.sh --server`.

5. Open the printed address, sign in using the bootstrap values described under **Credentials**, change the Admin password, and confirm the new login.
6. Clear both bootstrap values, restart, create named users in Settings, and make a first backup.

Team mode adds PostgreSQL, enables login, creates the first administrator only when no active admin exists, and disables demo loading by default. It publishes the web port on `CCM_WEB_BIND` (default `0.0.0.0`). Put it behind a TLS-terminating reverse proxy before allowing untrusted network access. The Compose file does not provide certificates, public DNS, firewall policy, or encrypted backups.

The launcher checks for unchanged placeholders, missing database/origin/host values, incomplete bootstrap pairs, and short bootstrap passwords before Compose starts. It does not expose secret values in its output.

Basic roles:

- Admin: workspace users, exports/restores, and all Editor actions.
- Editor: assessments, typed text resources, controls, mappings, documents, and evidence.
- Viewer: read-only access.

OIDC/SSO and MFA are future work, not implied by the current login.

## Configuration and persistence

Configuration comes from `.env`; `.env.example` documents the supported deployment values. Never commit `.env`.

Local volumes:

- `compliance-control-map_ccm_sqlite_data`: SQLite database.
- `compliance-control-map_ccm_file_data`: uploaded file bytes.

Team volume:

- `compliance-control-map_ccm_postgres_data`: PostgreSQL data.

Stopping or replacing containers does not remove these volumes. `docker compose down` preserves them; the explicit local refresh is the exception.

## Backup, restore, and portability

In local mode:

```powershell
.\launch.ps1 -Mode export -Archive data\workspace.zip
```

The archive contains structured workspace data, mappings, metadata, file digests, and uploaded bytes. To restore, start an untouched workspace with `CCM_LOAD_DEMO=false`, then run:

```powershell
.\launch.ps1 -Mode restore -Archive data\workspace.zip
```

Restore rejects an already-used workspace, unsafe ZIP paths, unexpected expansion, missing files, and digest mismatches. In team mode, an authenticated administrator uses Settings → Backup and portability. See [`docs/backup-and-restore.md`](docs/backup-and-restore.md).

### Promote genuine local work

Use this path when local demo/testing has turned into work worth keeping:

1. In local mode, remove records you do not want and export `workspace.zip` with the command above.
2. Configure a **fresh** server with `CCM_SERVER_LOAD_DEMO=false` and start it once with bootstrap Admin credentials.
3. Sign in as that Admin and restore the archive from **Settings → Backup and portability** before adding other users or changing workspace data.
4. Imported assignment identities remain disabled and receive no passwords; the server's bootstrap Admin remains the login account. Recreate only the real team accounts you need.
5. Verify several requirements, document/evidence downloads, and readiness totals. Then make a server backup and clear the bootstrap values.

The restore accepts a fresh team workspace containing only its active bootstrap Admin. Any other user or work data causes it to refuse the import, preventing an accidental merge.

## Framework packs

Framework content lives under `framework-packs/<slug>/`, not in application code. A pack has `manifest.yaml`, `domains.yaml`, and `requirements.yaml` and is validated before import. Imported versions are content-hashed and immutable; corrections ship as a new version.

See [`docs/framework-packs.md`](docs/framework-packs.md) and [`framework-packs/soc2/README.md`](framework-packs/soc2/README.md). Included SOC 2 text is concise, independently authored readiness guidance—not official AICPA criterion text, legal advice, or an audit opinion. Always consult current licensed source material and your CPA.

## Development

Backend setup and checks:

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m pytest tests -q
python -m ruff check app tests
python -m mypy app
```

Frontend setup and checks:

```powershell
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm test -- --run
corepack pnpm lint
corepack pnpm build
```

Real-browser checks (with the local app running):

```powershell
cd frontend
corepack pnpm exec playwright install chromium
corepack pnpm exec playwright test e2e/accessibility.spec.ts e2e/mvp-workflow.spec.ts
```

Complete deployment smoke tests run in isolated Compose projects and delete only their own labeled test volumes afterward:

```powershell
.\tests\smoke\local-mode.ps1
.\tests\smoke\server-mode.ps1
```

The server smoke test exercises PostgreSQL, login, Admin/Editor/Viewer permissions, upload/download integrity, the complete database-backed test suite, and browser role gates. The one skipped case is an intentionally SQLite-only connection pragma.

## Security and optional model assistance

See [`docs/security.md`](docs/security.md) for implemented safeguards, deployment responsibilities, and known limits. Uploads are validated and stored under randomized names outside the web root; file contents are never executed or rendered inline.

Model assistance always defaults off and is never required for core work. When an operator explicitly enables it, `backend/app/inference`, [`agents/`](agents/README.md), and [`skills/`](skills/README.md) provide a provider-neutral, OpenAI-compatible boundary with exact URL allowlisting, environment-only secret references, role/workspace checks, bounded read-only tools, exact context preview, per-run external-transfer consent, finite terminal states, and advisory proposals.

No model output saves automatically or changes status. Editors may put validated output into local form state and must complete the normal Save action. Stored attachment bytes are never sent. See [`docs/model-assistance.md`](docs/model-assistance.md) and the [`field-test checklist`](docs/field-test-checklist.md).
