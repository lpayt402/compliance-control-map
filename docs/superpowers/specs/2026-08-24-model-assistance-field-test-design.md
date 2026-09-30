# Model Assistance Field-Test Design

## Status and source

This design records the approved field-test specification from `ComplianceControl-Model-Assistance-Field-Test-Prompt.md` and the three required read-only reconnaissance reports. Model assistance is always optional: `CCM_INFERENCE_ENABLED=false` is the default and must leave the full compliance workspace usable.

## Product boundary

The compliance data model remains requirement → assessment → organizational control → documents/evidence/resources. One built-in `compliance-assistant` may run one repository-installed skill at a time and use only authorized, read-only tools. It may summarize or draft; it may not decide readiness, change operating status, claim assurance, read attachment bytes, write records, browse, execute code, or act externally.

## Architecture

- Keep `InferenceGateway` as the application boundary. Put Pydantic AI, OpenAI SDK, and provider-transport imports only in `backend/app/inference/`.
- Exact-pin `pydantic-ai-slim[openai]==2.33.0` only after a deterministic structured-output proof and a fake OpenAI Chat Completions streaming/tool proof pass under strict typing. If either proof fails, use the existing HTTP client stack for the same bounded loop; introduce no other framework.
- Persist workspace-scoped non-secret provider profiles and bounded model-run history through one additive migration. Portable workspace exports omit both; sanitized activity records only action/outcome metadata.
- Build and authorize context server-side from one selected requirement or control plus explicitly selected optional records. The exact preview and outbound serialization are identical and carry stable source references, deterministic omissions, and a digest.
- Require a fresh digest-bound confirmation for every non-local run. Attachment bytes and internal storage metadata are never eligible context.
- Stream CSRF-protected NDJSON from `POST /api/v1/inference/runs/stream`. The frontend uses `AbortController`; disconnect, Stop, timeout, and every error path persist exactly one terminal run state.

## Security boundary

- Exact normalized base-URL allowlisting is enforced on create, update, test, and run. Reject URL credentials, query, fragment, redirects, public plaintext, metadata/link-local/multicast/unspecified addresses, unsafe DNS results, proxy inheritance, and policy mismatches.
- Only `env:VARIABLE_NAME` secret references are accepted. Provider responses expose `CONFIGURED`, `MISSING`, or `NOT_REQUIRED`, never the reference or value.
- Provider mutations/tests are Admin-only. Runs are Admin/Editor-only. Viewers receive no assistance UI or run content. Every lookup filters by both ID and server-derived workspace ID; every tool reauthorizes the current principal and approved record scope.
- Hard defaults are four model turns, eight tool attempts, 60,000 context characters, 12,000 output characters, 90 seconds, one active run per actor, and two active runs per workspace. Server maxima cannot be raised by clients.
- Workspace content is labeled untrusted data. Safety relies on absent write/network/file/shell/SQL tools, registry intersection, repeated authorization, output/source validation, and bounded execution—not on prompt secrecy.

## User experience

- Settings replaces the disabled card with an Admin provider panel while retaining a clear disabled/unconfigured state.
- Requirement and control detail gain an Assist tab for Admin/Editor only. Optional context is unchecked by default; server-authored preview shows exactly what transfers.
- The run state machine is idle → preparing → running/stopping → completed, cancelled, timed out, or failed. Unexpected EOF and malformed NDJSON are failures; no indefinite spinner is possible.
- Structured proposals show sources and may update only local implementation-note or resource-form drafts. Existing normal Save buttons remain the sole mutation boundary. Unstructured or incomplete output is Copy-only.

## Research notes

- The repository is clean at `b5f08f320dabb4a3aead5cada59cf6cc197bce89`; backend 73 tests, frontend 27 tests, lint, type checking, build, migration, Playwright, and contract checks pass.
- Local and server Docker smokes currently fail before application startup because `docker/entrypoint-api.sh` checks out as CRLF on Windows; the Linux image resolves `/bin/sh\r`. Add an ops regression test, then enforce LF checkout.
- The current provider boundary and explicit export serializer are reusable, but current manifests are disabled-only and provider URLs/secret refs are too permissive.
- Current Pydantic documentation describes stable V2 structured output, tools, event streaming/cancellation, `TestModel`/`FunctionModel`, and `OpenAIChatModel` for OpenAI-compatible endpoints. PyPI identifies `pydantic-ai-slim` 2.33.0 as the current stable release on 2026-08-21.
- Viewer privacy is simplest and safest when the Assist tab and inference fetches are absent rather than rendered read-only.

## Rejected alternatives

- Transient-only runs: rejected because field feedback, terminal reconciliation, and bounded operational history are acceptance requirements.
- Stored API keys: rejected because secrets must remain external and request-time only.
- General chat, RAG/vector search, provider file search, MCP, multi-agent orchestration, and autonomous writes: rejected as outside the approved product boundary.
- Client-assembled context: rejected because it can diverge from server authorization, truncation, and external-transfer confirmation.
