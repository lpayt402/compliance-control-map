# Project guidance for coding agents

## Product boundary

Build a lightweight control-and-evidence workspace, not a full GRC suite. Protect the core path: framework requirement → assessment → organizational control → document/evidence. Keep framework-requirement status, organizational-control status, and evidence coverage separate.

SOC 2 is the first data pack, not a schema assumption. Domain logic and UI components must work with arbitrary framework slugs, versions, hierarchies, identifiers, and requirement mappings. Crosswalks describe relationships; they never copy readiness.

## Working rules

- Use test-driven development for behavior changes and reproduce bugs with a failing test first.
- Run server-side validation and workspace/role authorization for every mutation and object lookup.
- Preserve optimistic-concurrency revisions and append meaningful activity events.
- Treat uploaded names and bytes as hostile. Keep randomized storage keys, extension/type allowlists, size limits, digest checks, and traversal defenses.
- Never execute or render uploaded content inline. Downloads remain authenticated attachments.
- Keep local and PostgreSQL deployments on the same API and data model.
- Model assistance is permitted only as an optional, default-off, provider-neutral, bounded, advisory, and human-reviewed capability.
- Provider secrets must never be stored in the database. Store non-secret provider metadata and external `env:` secret references only, and resolve secret values at request time without returning, logging, exporting, or recording them in activity.
- Model tools must be read-only and must repeat the normal workspace, role, object, and selected-record authorization checks on every call. Record references are context, not authorization.
- Uploaded attachment bytes, extracted attachment content, downloads, exports, arbitrary network access, shell, SQL, external actions, and autonomous status changes are outside the model-assistance boundary for this release.
- Model output may populate local drafts only. No model result may write to the workspace or change requirement/control status without the user's normal reviewed Save action.
- Do not create or change GitHub remotes, push branches, add GitHub automation, or publish releases. Repository hosting belongs to the project owner.
- Never commit `.env`, databases, uploads, exports, credentials, or generated build output.

## Verification

From `backend`:

```powershell
python -m pytest tests -q
python -m ruff check app tests
python -m mypy app
```

From `frontend`:

```powershell
corepack pnpm test -- --run
corepack pnpm lint
corepack pnpm build
corepack pnpm exec playwright test
```

From the repository root:

```powershell
.\tests\ops\test-launch.ps1
.\tests\ops\test-compose.ps1
.\tests\ops\test-docs.ps1
docker compose --env-file .env -f docker-compose.yml config --quiet
docker compose --env-file .env -f docker-compose.yml -f docker-compose.server.yml config --quiet
```

Read [`docs/security.md`](docs/security.md) before changing auth, uploads, storage, exports, deployment, or the inference boundary.
