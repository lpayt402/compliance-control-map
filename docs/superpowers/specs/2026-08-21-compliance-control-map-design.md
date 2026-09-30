# Compliance Control Map — Product and Architecture Design

**Status:** Approved design baseline
**Date:** 2026-08-21
**Initial framework:** SOC 2 Trust Services Criteria, 2017 edition with revised points of focus (2022)
**Product boundary:** Single-workspace, self-hosted compliance readiness and evidence tracker

## 1. Product intent

Compliance Control Map is a lightweight control and evidence workspace where compliance frameworks are different lenses over the same underlying security program. SOC 2 is the first populated lens; the application is not a SOC 2-specific schema or a full governance, risk, and compliance platform.

The MVP answers six questions quickly:

1. Where are we?
2. What is missing?
3. Who owns it?
4. How do we satisfy it?
5. What policies support it?
6. What evidence proves it?

The primary workflow is:

> Assess → Assign → Document → Map → Attach Evidence → Track

The framework map is the signature interface. The product must remain understandable to a practitioner who is not a developer or a GRC specialist.

## 2. Scope

### 2.1 MVP capabilities

- Run from one repository in local or team/server mode.
- Launch local mode with one command and no external services.
- Import versioned, framework-agnostic framework packs.
- Ship a complete initial SOC 2 pack covering Common Criteria plus Availability, Confidentiality, Processing Integrity, and Privacy criteria.
- Show requirements as a searchable, filterable Navigator-style status map.
- Maintain workspace-specific requirement assessments separately from framework definitions.
- Create lightweight organizational controls and map them many-to-many to requirements.
- Track status, applicability, owner, assignee, due date, tags, and implementation notes.
- Upload documents and evidence once and map them many-to-many to controls or directly to requirements.
- Show a table-based Tracker view over the same data.
- Show readiness, assessed coverage, gaps, overdue work, missing mappings, and recent activity.
- Maintain basic users, sessions, and Admin, Editor, and Viewer roles in team mode.
- Export a portable structured backup with file metadata and stored artifacts.
- Store generic cross-framework requirement mappings and expose their API, while deferring the overlay UI.

### 2.2 Explicitly deferred

- Additional populated framework packs
- Overlay and crosswalk visualization
- Automated evidence collection or parsing
- Continuous control monitoring
- SIEM, cloud, vendor, ticketing, or audit-portal integrations
- Complex approvals, workflows, or a policy authoring suite
- OIDC/SSO
- S3 or other object-storage implementations
- Model inference, AI assistants, or automated compliance decisions
- Electron or Tauri packaging

Deferred capabilities receive extension seams where they materially avoid a later rewrite. They do not receive speculative UI or runtime dependencies.

## 3. Research notes

- The current AICPA resource remains the **2017 Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy with revised points of focus (2022)**. The full identifier surface contains 61 criteria: 33 Common Criteria, 3 Availability, 5 Processing Integrity, 2 Confidentiality, and 18 Privacy. The pack will use `2017-tsc-pof-2022` as its source version and record its verification date. Source: <https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022>
- AICPA and COSO licensing terms make redistribution of official criteria, points of focus, COSO text, logos, or PDFs risky. The product will bundle independently authored, non-authoritative readiness summaries, link to the official source, avoid logos and endorsement claims, and state that licensed/current materials and a CPA govern an audit. Sources: <https://www.aicpa-cima.com/help/terms-and-conditions> and <https://www.coso.org/_files/ugd/3059fc_f7d01f2bbf7f46528d8fd2fe1207b5fd.pdf>
- MITRE ATT&CK Navigator validates category columns, compact selectable tiles, layered annotations, search/filtering, and progressive disclosure. The MVP will retain that mental model while using categorical readiness states rather than numeric heat gradients. Source: <https://github.com/mitre-attack/attack-navigator/blob/master/USAGE.md>
- WAI guidance requires status to be expressed with text or glyphs in addition to color, keyboard operability, visible focus, accessible status messages, and correct table semantics. The map will use native controls plus grouped arrow-key navigation; the Tracker will remain a native table. Sources: <https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html> and <https://www.w3.org/WAI/ARIA/apg/patterns/grid/>
- FastAPI, SQLAlchemy 2, and Alembic provide the cleanest database-portable modular monolith. Alembic supports SQLite batch migrations, while Prisma does not share migration files across SQLite and PostgreSQL providers. Sources: <https://alembic.sqlalchemy.org/en/latest/batch.html> and <https://www.prisma.io/docs/orm/prisma-migrate/understanding-prisma-migrate/limitations-and-known-issues>
- OpenAI's current Responses API supports model responses, structured outputs, custom function tools, MCP tools, and tool-choice constraints. A future provider-neutral inference gateway can map to this surface without making OpenAI a core application dependency. Source: <https://developers.openai.com/api/reference/cli/resources/responses/methods/create>

## 4. Architecture

### 4.1 Deployment shape

The browser always communicates with an HTTP API. Production uses one origin:

```text
Browser → web/reverse-proxy :3000
          ├── /             static React/Vite build
          └── /api/v1       FastAPI
                              ├── SQLAlchemy → SQLite or PostgreSQL
                              └── FileStorage → local filesystem
```

The backend is a modular monolith. Frameworks, assessments, controls, libraries, authentication, activity, and export are modules with explicit service boundaries inside one deployable API process. This keeps transactions simple, avoids distributed-system overhead, and permits later extraction only if real scale requires it.

### 4.2 Technology choices

- **Frontend:** React, TypeScript, Vite, React Router, TanStack Query, CSS custom properties, and a small accessible primitive layer.
- **Backend:** Python, FastAPI, Pydantic, synchronous SQLAlchemy 2, Alembic, and psycopg 3.
- **Local database:** SQLite with one API worker and database files on a local named volume.
- **Team database:** PostgreSQL with shared persistent storage.
- **Files:** `FileStorage` protocol with `LocalFilesystemStorage` in V1.
- **Contract:** versioned REST API under `/api/v1`, documented by OpenAPI. Frontend client types are generated from the backend schema.
- **Production web:** static frontend and reverse proxy in the `web` image, routing `/api/v1` to the API.

SQLite write-ahead logging is not placed on a multi-host network filesystem. Team mode uses PostgreSQL.

### 4.3 Repository shape

```text
/
├── frontend/
├── backend/
├── framework-packs/
│   └── soc2/
├── agents/                 # future inference manifests; no V1 runtime
├── skills/                 # future model-facing capabilities; no V1 runtime
├── data/
├── docker/
├── docs/
├── tests/
├── AGENTS.md               # repository guidance for coding agents
├── docker-compose.yml
├── docker-compose.server.yml
├── launch.ps1
├── launch.sh
├── .env.example
└── README.md
```

`AGENTS.md` governs development agents working on the repository. Runtime agent profiles live under `agents/` and are intentionally separate.

## 5. Domain model

### 5.1 Boundary principles

- All entities use internal UUIDs.
- Human/external identifiers are attributes, never primary keys.
- Framework versions are immutable after import.
- Catalog definitions are separated from workspace-specific state.
- Mutable organizational records carry `workspace_id`, even though V1 exposes one workspace per deployment.
- Status, control maturity, and evidence coverage remain independent.
- Many-to-many relationships use association records, not JSON ID arrays.
- Mutable aggregate roots use an integer revision for optimistic concurrency.

### 5.2 Catalog entities

**Framework**

- `id`, `slug`, `name`, `description`, timestamps

**FrameworkVersion**

- `id`, `framework_id`, `version`, `source_uri`, `source_hash`, `verified_on`, `published_at`, `imported_at`, `is_active`
- Unique on `(framework_id, version)`.
- Imported definitions cannot be silently edited. A changed pack creates a new version.

**FrameworkDomain**

- `id`, `framework_version_id`, `external_id`, `name`, `description`, `parent_id`, `sort_order`

**FrameworkRequirement**

- `id`, `framework_version_id`, `domain_id`, `parent_id`, `external_id`, `title`, `summary`, `guidance`, `sort_order`, `source_reference`, timestamps
- Unique on `(framework_version_id, external_id)`.
- `summary` is an original description of intended outcome. Optional `guidance` contains clearly labeled illustrative examples and is never presented as official criterion text.

### 5.3 Workspace entities

**Workspace**

- Singleton V1 record with `id`, `name`, locale/time-zone settings, timestamps.

**RequirementAssessment**

- `id`, `workspace_id`, `requirement_id`, `status_code`, `applicability`, `owner_user_id`, `assignee_user_id`, `due_date`, `implementation_notes`, `revision`, timestamps
- Unique on `(workspace_id, requirement_id)`.
- Applicability values: `UNDETERMINED`, `APPLICABLE`, `NOT_APPLICABLE`.
- Setting status to `NOT_APPLICABLE` synchronizes applicability; changing back requires a non-N/A status.

**StatusDefinition**

- `id`, `workspace_id`, `scope`, `code`, `label`, `description`, `color_token`, `icon`, `sort_order`, `is_terminal`
- Requirement codes seeded as `NOT_ASSESSED`, `GAP`, `IN_PROGRESS`, `PARTIAL`, `READY`, and `NOT_APPLICABLE`.
- Labels, descriptions, order, and palette may be customized. Core status semantics are stable so dashboards and exports remain portable.
- Control codes seeded as `PLANNED`, `IMPLEMENTING`, `OPERATING`, `NEEDS_ATTENTION`, and `RETIRED`.

**OrganizationalControl**

- `id`, `workspace_id`, `code`, `name`, `description`, `status_code`, `owner_user_id`, `implementation_notes`, `revision`, timestamps
- Lightweight in V1. It is not a workflow, test procedure, or audit object.

**RequirementControlMapping**

- `id`, `requirement_id`, `control_id`, `coverage`, `rationale`, timestamps
- Many requirements may use one control and one requirement may need multiple controls.
- `coverage` is descriptive and does not transfer readiness.

**RequirementMapping**

- `id`, `source_requirement_id`, `target_requirement_id`, `relationship_type`, `confidence`, `mapping_source`, `notes`, `created_by`, timestamps
- Relationship types: `EQUIVALENT`, `STRONG_OVERLAP`, `PARTIAL_OVERLAP`, `RELATED`.
- Directed semantics: the record describes how the source is related to the target. An inverse display may be derived, but no automatic inverse row is created.
- Endpoints must differ; duplicate directed mappings are rejected.
- `confidence` is optional and represented as an integer 0–100 plus provenance, not an automated compliance score.

### 5.4 Library entities

**Document**

- `id`, `workspace_id`, `stored_file_id`, `name`, `document_type`, `description`, `version`, `effective_date`, `owner_user_id`, `notes`, `revision`, timestamps
- Seeded document types are `POLICY`, `STANDARD`, `PROCEDURE`, `PLAN`, `GUIDELINE`, and `OTHER`.

**Evidence**

- `id`, `workspace_id`, `stored_file_id`, `name`, `description`, `evidence_date`, `owner_user_id`, `notes`, `revision`, timestamps

**StoredFile**

- `id`, `workspace_id`, `storage_key`, `original_filename`, `normalized_extension`, `declared_media_type`, `detected_media_type`, `byte_size`, `sha256`, `uploaded_by`, timestamps
- `storage_key` is opaque and randomized. Absolute paths are never trusted database values.

Documents and evidence each reference one stored file in V1. Replacing a file creates a new `StoredFile` and preserves activity history.

Association records support:

- control ↔ document
- control ↔ evidence
- requirement ↔ document
- requirement ↔ evidence

Control mappings are the normal path. Direct requirement mappings support framework-specific narratives and artifacts.

### 5.5 Users, sessions, tags, and activity

**User** contains normalized email, display name, password hash when local auth is enabled, `can_login`, role, disabled state, and timestamps. Local/no-auth workspaces may create named owner/assignee records with `can_login=false` so assignment does not require creating credentials.

**Session** stores only a hash of the opaque session secret, user, CSRF secret, expiry, last-seen time, and revocation state.

**Tag** and typed association records support requirements and controls without embedding arrays.

**RequirementNote** contains assessment, body, author, created timestamp, and edited timestamp. User-authored notes are displayed chronologically with system activity but remain distinguishable from system-generated events.

**ActivityEvent** is append-only and contains workspace, actor, entity type and ID, action code, safe before/after snapshots, and timestamp. Snapshots exclude secrets and stored file contents. Events cover status, assignment, notes, mapping, upload, and delete/archive changes.

## 6. Framework packs

Framework content is isolated under `framework-packs/<slug>/`. A pack contains a YAML or JSON manifest, domains, requirements, source metadata, and validation fixtures.

```yaml
framework:
  id: soc2
  name: SOC 2 Trust Services Criteria
  version: 2017-tsc-pof-2022
  source_uri: https://www.aicpa-cima.com/...
  verified_on: 2026-08-21
  disclaimer: Independent, non-authoritative readiness summaries.

domains:
  - id: CC6
    name: Logical and Physical Access Controls
    sort_order: 60

requirements:
  - id: CC6.1
    domain: CC6
    title: Logical access safeguards
    summary: Establish safeguards that restrict logical access according to authorized responsibilities.
    guidance: Illustrative practices can include approved access requests, role-based access, periodic review, and prompt revocation.
```

The SOC 2 pack includes these identifier ranges:

- Common Criteria: `CC1.1–CC1.5`, `CC2.1–CC2.3`, `CC3.1–CC3.4`, `CC4.1–CC4.2`, `CC5.1–CC5.3`, `CC6.1–CC6.8`, `CC7.1–CC7.5`, `CC8.1`, `CC9.1–CC9.2`
- Availability: `A1.1–A1.3`
- Processing Integrity: `PI1.1–PI1.5`
- Confidentiality: `C1.1–C1.2`
- Privacy: `P1.1`, `P2.1`, `P3.1–P3.2`, `P4.1–P4.3`, `P5.1–P5.2`, `P6.1–P6.7`, `P7.1`, `P8.1`

Each summary receives a two-pass review against the current authoritative resource. It describes intended outcome without copying official text, COSO wording, or points of focus. Prescriptive examples appear only in the separate guidance field. The UI and README state:

> Independent, non-authoritative readiness summaries. Not AICPA criteria, legal advice, or an audit opinion. Consult the current AICPA Trust Services Criteria and your CPA.

Optional demo organizational data is separate from the framework pack and clearly labeled. It includes at least `CC6.1 — Ready`, `CC6.2 — Partial`, `CC7.1 — Gap`, and `CC8.1 — In Progress`, example assignments, one lightweight control, and small `.txt` placeholder uploads whose filenames and contents explicitly say they are demo-only. It includes no pretend official policies or unlabeled binary evidence.

## 7. API contract

All routes are versioned under `/api/v1`. Successful responses use `{ "data": ..., "meta": ... }`. Errors use `application/problem+json` with stable type, title, status, detail, and request ID. Validation errors never expose stack traces or internal paths.

Primary resources:

- `/frameworks`, `/frameworks/{id}`, `/frameworks/{id}/versions`
- `/requirements`, `/requirements/{id}`, `/requirements/{id}/assessment`
- `/requirements/{id}/notes`
- `/controls`, `/controls/{id}`, `/requirements/{id}/controls`
- `/requirement-mappings`, `/requirements/{id}/mappings`
- `/documents`, `/documents/{id}`, `/documents/{id}/file`
- `/evidence`, `/evidence/{id}`, `/evidence/{id}/file`
- `/requirements/{id}/documents`, `/requirements/{id}/evidence`
- `/controls/{id}/documents`, `/controls/{id}/evidence`
- `/users`, `/sessions`, `/auth/login`, `/auth/logout`, `/auth/csrf`
- `/dashboard`, `/activity`
- `/exports`, `/exports/{id}/download`
- `/health/live`, `/health/ready`

List endpoints support search, filters, sorting, and bounded pagination. OR applies within a facet and AND across facets. Mutating aggregate endpoints require the current `revision` or `If-Match`; stale writes return `409 Conflict` with the current representation.

Uploads are multipart requests with CSRF protection and server-side streaming limits. Downloads are authorization-checked and returned as attachments.

OpenAPI is generated by FastAPI and used to generate frontend types. The API is initially internal to the browser client, but versioning prevents the future desktop wrapper from depending on unversioned routes.

## 8. Product experience

### 8.1 Visual system

The approved direction is **Field Manual**: a warm mineral-paper surface, deep forest ink, restrained rust accent, editorial display type, compact sans-serif working type, ledger rules, shallow corners, and flat information layers. Status is expressed through controlled color, text, glyph, and edge treatment.

The system deliberately avoids generic nested white cards, oversized radii, glass panels, gradient-heavy hero areas, and ornamental dashboards. One signature element—the framework atlas/ledger treatment—carries across map headings, domain coordinates, activity history, and export covers.

The voice is a serious instrument with a slightly mischievous operator. Humor is limited to empty states, tips, demo content, and harmless easter eggs. It never appears in destructive confirmations, permission errors, status definitions, evidence provenance, legal disclaimers, or security warnings.

### 8.2 Navigation

Primary navigation remains:

```text
Dashboard
Framework Map
Tracker
Documents
Evidence
Settings
```

Controls are first-class data but do not get a heavyweight top-level module in V1. Users reach controls through requirement details and relationship links. Direct control URLs remain bookmarkable.

### 8.3 Dashboard

The dashboard shows:

- Ready, Partial, In Progress, Gap, Not Assessed, and Not Applicable counts
- Overall readiness percentage
- Assessed percentage
- Missing documentation queue
- Missing evidence queue
- Overdue requirements
- Gap requirements
- Recent changes

Overall readiness is:

```text
READY requirements ÷ all requirements not marked NOT_APPLICABLE
```

Partial and in-progress requirements receive no invented fractional credit. Assessed rate is displayed separately so a user can distinguish completion of assessment from readiness.

### 8.4 Framework Map

- Full-canvas, framework-agnostic view grouped by generic domains.
- Tiles show external ID, status label and glyph, and document/evidence counts.
- Parent requirements use disclosure controls for optional child requirements; expand-all and collapse-all are available without changing data order.
- Search covers identifier, title, summary, and tags.
- Filters cover status, domain, owner, assignee, applicability, tags, and due state.
- Active filters appear as removable tokens with result count and clear-all action.
- The map receives injected status definitions and an `annotations` collection. V1 passes an empty annotation list; future crosswalk coverage appears through this separate channel without changing readiness styling.
- Each domain is a named region. One roving tab stop per domain and arrow keys navigate tiles; Enter or Space opens details.

Document and evidence counts are unique record counts across direct mappings and mappings inherited through linked controls. A record reachable by both paths is counted once. The detail sheet labels direct and control-derived coverage so the number is explainable.

Selecting a tile opens a modal detail sheet approximately 72–74% of viewport width on desktop and 88% on tablets. Phones use a full-screen sheet. The background is inert; Escape closes; focus is contained and restored to the selected tile.

### 8.5 Requirement detail

The sheet has tabs:

- **Overview:** official identifier, independent summary, source link, status, applicability, ownership, due date, tags, and implementation notes
- **Controls:** create/link lightweight organizational controls and explain coverage
- **Documents:** mapped policy/procedure records, including indirect control coverage and direct requirement mappings
- **Evidence:** mapped evidence, including indirect and direct coverage
- **Activity:** notes and append-only meaningful changes

Editors can make focused changes and save explicitly. Unsaved state is visible; stale revisions receive a conflict prompt instead of silent overwrite.

### 8.6 Tracker and libraries

Tracker uses a semantic table with identifier, title, status, owner, assignee, due date, document count, evidence count, and last updated. It supports filtering, search, accessible sorting, and inline status changes.

Documents and Evidence each have a central library with upload, metadata, relationship counts, filtering, and detail pages. Mapping uses a searchable multi-select over controls and requirements; the file is stored once.

## 9. Authentication and authorization

`AUTH_MODE` supports:

- `disabled`: local development/single-user mode only
- `local`: password-backed users and server-side sessions

No-auth mode binds to loopback by default. Exposing it beyond loopback requires an explicit insecure override and produces a persistent warning.

Credential verification sits behind an identity-provider service boundary so a later OIDC adapter can coexist with local accounts. No OIDC routes or dependencies ship in V1.

Team mode uses opaque server-side sessions rather than browser-stored JWTs. The cookie contains a cryptographically random session secret; the database stores only its hash. Production uses a `__Host-` cookie with `Secure`, `HttpOnly`, `SameSite=Lax`, and `Path=/`.

Unsafe methods require a synchronizer CSRF token in a custom header and pass an Origin check. Login regenerates sessions; logout, user disable, password reset, and role change invalidate relevant sessions.

Passwords use Argon2id. The verifier accepts at least 64 characters, uses a 15-character minimum for single-factor accounts, allows paste and Unicode, avoids composition rules and forced periodic rotation, and supports compromised-password screening when network policy permits.

Login attempts are throttled by account and source, authentication errors do not reveal whether an account exists, and a missing-user path performs a dummy password-hash verification to reduce timing differences.

Permissions:

| Capability | Admin | Editor | Viewer |
|---|---:|---:|---:|
| View workspace data | Yes | Yes | Yes |
| Change assessments and controls | Yes | Yes | No |
| Upload/map documents and evidence | Yes | Yes | No |
| Add notes | Yes | Yes | No |
| Manage users, roles, settings | Yes | No | No |
| Export backup | Yes | No | No |
| Restore/reset data | Local operator only | No | No |

Server-side dependencies enforce authorization on every route. UI hiding is convenience only.

## 10. File storage and upload security

`FileStorage` accepts a stream and returns an opaque storage key. `LocalFilesystemStorage` writes under a configured storage root outside the webroot.

Upload handling:

1. Normalize and preserve the original filename only as metadata.
2. Reject traversal patterns, control characters, reserved device names, unsupported extensions, and oversized bodies.
3. Stream to a temporary file under the storage root while enforcing the byte limit and computing SHA-256.
4. Validate declared type, extension, and file signature where practical.
5. Atomically rename to a randomized internal key.
6. Create metadata and mapping records transactionally; clean up orphaned temporary files on failure.

Allowed types default to PDF, DOCX, XLSX, CSV, TXT, common images, ZIP, and JSON. The default limit is configurable and conservative. ZIP files are stored but never unpacked. Uploaded content is never executed or rendered inline. Downloads use `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.

Proxy and application body limits both apply. Authorization occurs before metadata or file bytes are returned.

CORS is disabled in the normal same-origin deployment. Operators must explicitly list trusted origins before a separate-origin client is accepted; wildcard origins are not permitted with credentials.

## 11. Launch, persistence, and deployment

### 11.1 Local operator workflow

Windows:

```powershell
.\launch.ps1
```

Linux/macOS:

```bash
./launch.sh
```

The launcher:

1. Checks Docker and Compose.
2. Creates `.env` from `.env.example` when missing.
3. Starts the local Compose stack.
4. Waits for migrations and readiness checks.
5. Loads the framework pack idempotently.
6. Optionally loads demo organizational data.
7. Prints `http://localhost:3000` and basic status/help.

Local Compose uses named volumes for SQLite and stored files. Containers may be replaced without data loss.

### 11.2 Testing reset

Windows uses `-Refresh`; POSIX uses `--refresh`. Refresh:

- works only in local SQLite mode;
- names the exact application database and storage volumes before deletion;
- requires an interactive confirmation unless `-Yes`/`--yes` is supplied;
- refuses unknown Compose projects or server/PostgreSQL mode;
- removes only this application's local data volumes;
- recreates the stack, reloads the framework pack, and loads demo data when configured.

Refresh does not delete repository files, unrelated Docker resources, or external server data.

### 11.3 Team mode

Team mode overlays `docker-compose.server.yml`, supplies a PostgreSQL `DATABASE_URL`, enables local authentication, and uses persistent/shared file storage. The API image and migrations are identical to local mode. A migration service completes before the API becomes ready.

## 12. Export and restore

An Admin can create a versioned export archive containing:

- manifest and application schema version
- framework/version metadata
- assessments, controls, mappings, tags, notes, and activity metadata
- document/evidence metadata and hashes
- stored file bytes in a content-addressed archive area

Exports exclude password hashes, session records, CSRF secrets, model/API secrets, and server-only configuration.

V1 restore is an operator command for a new or explicitly empty local installation. It validates archive version, paths, hashes, and uniqueness before writing. Restoring into a populated workspace is deferred to avoid unsafe merge semantics.

## 13. Multi-framework and overlay extension

Multiple framework versions may coexist from day one. The current UI selects one base framework, but its map consumes generic domains, requirements, assessments, counts, and independent annotations.

Crosswalks describe coverage relationships, not compliance inheritance. Future overlay annotations may show:

```text
CC6.1
READY
NIST CSF · 3 mappings
PCI DSS · 2 mappings
```

The overlay derives counts from `RequirementMapping` records and shows provenance. It never changes the assessment status. Queries can later identify controls that support the most frameworks, uncovered requirements, shared evidence, and incremental framework effort without duplicating controls or files.

## 14. Future inference extension seam

Inference is disabled and absent from the V1 user experience. The repository reserves a provider-neutral boundary:

```text
Application services
        ↓
InferenceGateway
   ├── OpenAI Responses adapter
   ├── OpenAI-compatible/local adapter
   └── future provider adapters

AgentProfile
   ├── versioned instructions
   ├── allowed skills
   ├── allowed tools
   └── data scopes
```

A future provider connection contains provider type, base URL or IP, model identifier, capability flags, timeouts, TLS policy, data-retention policy, and a secret reference. Secret values live in an environment/secret provider or encrypted secret store and never appear in normal API responses, exports, activity snapshots, or prompts.

Future runtime conventions:

- `agents/<id>/agent.yaml` defines identity, version, instructions, skill allowlist, and scopes.
- `skills/<id>/SKILL.md` plus a manifest defines a bounded capability, input/output schema, required permissions, and data handling.
- `InferenceGateway` exposes structured generation, streaming, and tool-call events without leaking provider response objects into domain services.
- Adapters advertise capabilities; the application does not assume every provider supports tools, images, streaming, or structured output.
- Models are advisory by default. They cannot change readiness, mappings, controls, or evidence without an explicit user-confirmed application action.
- Access is least-privilege and read-only by default. Sending document or evidence contents off-host requires provider policy and explicit user action.
- Every request records actor, provider/model identifier, skill version, scoped record IDs, token/latency metadata when available, outcome, and safe provenance. Prompts, secrets, and evidence bodies are not indiscriminately logged.
- Provider failures cannot corrupt domain transactions. Suggested changes are validated through the same APIs and authorization rules as human changes.

V1 may include interface definitions and explanatory manifests only. It makes no network inference calls and stores no provider credentials.

## 15. Error handling and operational behavior

- Domain validation returns actionable, safe problem responses.
- Not-found and forbidden behavior avoids leaking sensitive record existence where applicable.
- Request IDs flow through proxy, API logs, and problem responses.
- Database writes are transactional; file writes use staged cleanup.
- Stale revisions return conflict rather than last-write-wins.
- Framework imports validate the complete pack before committing any definitions.
- Import is idempotent by framework, version, and source hash.
- Deleting a mapped document or evidence record requires explicit confirmation; V1 prefers archive/soft-delete when relationships exist.
- Health endpoints distinguish process liveness from database/storage readiness.
- Security headers include CSP appropriate to a static same-origin SPA, frame denial, referrer policy, permissions policy, HSTS in TLS deployments, and `nosniff`.

## 16. Testing and verification

The project uses test-first development for behavior. Meaningful automated coverage includes:

- framework pack schema validation, 61-criterion count, identifier uniqueness, and idempotent loading
- requirement assessment CRUD, status/applicability synchronization, ownership, tags, and optimistic concurrency
- user-authored requirement notes and their ordering alongside immutable activity events
- readiness and assessed-rate calculations
- organizational control CRUD and many-to-many requirement mappings
- directed requirement crosswalk validation and provenance
- document and evidence CRUD, direct mappings, control mappings, relationship counts, and deduplication behavior
- file extension/type/signature/size/path validation, randomized storage keys, authorization, and cleanup on failure
- Admin, Editor, Viewer, disabled-auth, session, CSRF, and route-level permission behavior
- export manifest completeness, secret exclusion, hash validation, and empty-workspace restore
- SQLite migrations and API suite
- PostgreSQL migrations and API suite against a real service
- React component and accessibility tests for status tiles, filters, detail sheet focus, Tracker sorting, and forms
- browser-level MVP workflow from map selection through upload, mapping, dashboard update, restart persistence, and local refresh
- Docker Compose configuration and health smoke tests

Completion claims require fresh evidence from backend tests, frontend tests, production builds, database migration tests, and an end-to-end Docker smoke test.

## 17. Acceptance criteria

The MVP is accepted when a non-developer can:

1. Run one launcher command and open the app at `http://localhost:3000`.
2. View all SOC 2 criteria as the Field Manual framework map.
3. Search and filter the map without losing context.
4. Open a requirement in the responsive detail sheet.
5. update readiness, applicability, owner, assignee, due date, tags, and implementation notes.
6. Create or map a lightweight organizational control.
7. Upload a document once and map it to multiple controls or requirements.
8. Upload evidence once and reuse it through the same mapping model.
9. Inspect relationships from requirements, controls, documents, and evidence.
10. Operate the Tracker and understand dashboard readiness calculations.
11. Restart containers without losing database or files.
12. Export a portable backup and restore it into an empty local installation.
13. Use `-Refresh`/`--refresh` to reset only local test data after confirmation.
14. Configure the same application for PostgreSQL team mode with Admin, Editor, and Viewer users.
15. Store and query basic cross-framework mappings without an overlay UI.

## 18. One-way doors and migration paths

The approved one-way doors are:

- **Modular monolith over microservices:** simplest transactional boundary. Modules can be extracted later behind existing service/API interfaces if scale proves it necessary.
- **FastAPI/SQLAlchemy/Alembic:** selected for validation, OpenAPI, and cross-database migrations. The REST contract and generated client isolate the frontend from backend implementation.
- **Immutable framework versions:** prevents silent historical drift. A later pack creates a new version and an explicit assessment migration tool.
- **Separate definitions, assessments, controls, and evidence coverage:** adds several joins now but avoids an expensive multi-framework rewrite later.
- **Opaque server sessions:** favors same-origin security and revocation. A later desktop or external API can add a separate token flow without replacing browser sessions.
- **Single-workspace deployment with workspace keys:** keeps V1 understandable while preserving a migration path to stronger workspace isolation. Multi-tenancy would require authorization and operational work, not a wholesale schema rewrite.
- **Local storage protocol:** avoids premature object-store dependency. Stored opaque keys and streaming APIs allow an S3-compatible backend later.
- **Provider-neutral inference gateway:** prevents future model-specific objects from leaking into the compliance domain. It remains disabled until a separately designed AI feature is approved.

These trade-offs have been reviewed against the product's priority: make the framework → assessment → organizational control → document/evidence workflow excellent before adding breadth.
