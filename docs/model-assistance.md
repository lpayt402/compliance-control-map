# Optional model assistance

Model assistance is an optional, default-off field-test feature. ComplianceControl remains fully usable when it is disabled, unavailable, or misconfigured. Output is advisory: it cannot change requirement readiness, control operating status, evidence coverage, notes, or playbooks. An Editor must deliberately place a validated proposal into local form state and then use the existing Save action.

This feature does not provide an audit opinion, certification, assurance conclusion, legal advice, or proof that a control operates effectively.

## Supported provider protocol

The provider gateway supports the OpenAI-compatible Chat Completions protocol at an exact allowlisted base URL. Streaming is supported. Tool calls and structured output are used only when the profile declares them; profiles without either capability fall back to bounded read-only context and advice-only text. Invalid structured output remains copyable but cannot use field-specific draft actions.

The application does not expose a general URL fetcher, shell, filesystem reader, SQL tool, arbitrary tool registry, or autonomous agent. Four installed skills are available:

- Requirement Summary and Next Actions
- Draft Implementation Notes
- Draft Evidence-Collection Playbook
- Control Review

Each installed manifest is validated at startup. A bad or escaping manifest makes assistance fail closed when the feature is enabled.

## Enable a local provider

The global kill switch defaults to `false`. In `.env`, use an exact endpoint:

```dotenv
CCM_INFERENCE_ENABLED=true
CCM_INFERENCE_ALLOWED_BASE_URLS=["http://host.docker.internal:11434/v1"]
```

Restart the containers, open **Settings → Model providers** as an Admin, and create a profile similar to:

```text
Profile ID: local-ollama
Base URL: http://host.docker.internal:11434/v1
Model ID: qwen3:8b
TLS policy: Plaintext local only
Data policy: Local only
Secret reference: blank
```

Declare only capabilities the selected model actually supports. Save the profile, test it, then enable it. An enabled default profile must also be enabled globally, exactly allowlisted, and have a resolvable secret reference when one is configured.

### Docker Desktop, Linux, and WSL

`docker-compose.yml` maps `host.docker.internal` to the Docker host. On Docker Desktop for Windows/macOS and on Linux with the supplied host-gateway entry, the API-container URL for host Ollama is:

```text
http://host.docker.internal:11434/v1
```

If Ollama is running in WSL while Docker Desktop owns the containers, ensure the provider listens on an interface reachable from Docker, not only WSL loopback. A typical Ollama host setting is `OLLAMA_HOST=0.0.0.0:11434`; restrict the host firewall to trusted local interfaces. Verify from the API container before changing the application allowlist:

```powershell
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/v1/models', timeout=5).status)"
```

That diagnostic contacts only the endpoint you specify. Do not broaden the application allowlist to compensate for a network-listening problem.

## Enable an explicitly hosted provider

Allow only the exact HTTPS base URL and provide its credential through the process environment:

```dotenv
CCM_INFERENCE_ENABLED=true
CCM_INFERENCE_ALLOWED_BASE_URLS=["https://models.example.com/v1"]
CCM_MODEL_API_KEY=replace_with_the_real_environment_secret
```

Create the profile with `env:CCM_MODEL_API_KEY` as its secret reference. The database and API response store the reference name and a configured/missing status, never the value. `.env` is ignored by Git and must be protected like any other deployment secret.

Use **TLS required** for a public hosted endpoint. **Private CA allowed** still requires HTTPS and validates against the API container's trust store; install the private CA in a locally maintained image. It does not disable certificate verification. Plain HTTP is accepted only for a local-only profile whose exact destination resolves to a permitted local address.

Provider requests disable proxy-environment inheritance, reject redirects, revalidate DNS at use, and block credentials in URLs, query strings, fragments, traversal, metadata endpoints, link-local, multicast, unspecified, and unlisted destinations. Exact base-URL allowlisting is intentional.

## What a run can include

Before every run, the Editor sees the exact rendered context and its digest. Context is limited to the selected requirement or control, mapped requirement/control facts when selected, typed note/playbook/contact text when selected, and document/evidence metadata. Source references identify the included records. The renderer applies a deterministic character budget and reports omissions.

Stored attachment bytes are never included, opened, rendered inline, or sent to a provider. Workspace text is explicitly marked untrusted so instructions embedded in record text remain data.

For every provider whose data policy is not `LOCAL_ONLY`, the UI shows the provider/model, destination, selected record types, typed-resource inclusion, and attachment-byte exclusion. The Editor must confirm that exact transfer again for every run. Changing any context option invalidates the preview and confirmation.

## Roles and human review

- Admins create, test, enable, disable, select defaults, and delete provider profiles. They can also run assistance.
- Editors can preview context, initiate bounded runs, stop them, copy results, apply structured proposals to local draft fields, and leave local feedback.
- Viewers cannot fetch assistance configuration, initiate runs, or apply drafts.

Provider mutations and run creation retain normal CSRF, origin, role, workspace, record-lookup, and optimistic-concurrency protections. Read-only tool calls repeat workspace and role checks for each call and can access only references approved for that run.

## Limits and terminal states

Default limits are 60,000 context characters, 12,000 output characters, four model iterations, eight tool calls, 90 seconds, one active run per user, and two active runs per workspace. Environment settings may lower or raise them only within server validation bounds. Every accepted run is finalized as `COMPLETED`, `CANCELLED`, `TIMED_OUT`, or `FAILED`.

The active-run limiter is process-local in this field-test release. Run one API process or add a shared limiter before multi-worker scale-out. Usage/cost accounting depends on provider protocol support and is not a billing control.

Run output and validated structured results are stored in the workspace run-history table so users can review and rate the field test. General activity stores only safe identifiers and outcomes—not prompts, context, output, secrets, tokens, raw errors, headers, or provider payloads. Provider profiles and run history are deliberately excluded from workspace backup exports; reconfigure providers after restore.

## Troubleshooting

- **Assistance disabled:** set `CCM_INFERENCE_ENABLED=true`, restart, and confirm `/api/v1/health/ready` remains ready.
- **Configuration error:** validate the installed `agents/` and `skills/` files and their referenced instruction/schema paths.
- **Destination blocked:** compare the normalized profile URL with the exact `CCM_INFERENCE_ALLOWED_BASE_URLS` entry. Do not add wildcards.
- **Secret missing:** confirm the profile uses `env:NAME` and that `NAME` exists inside the API container. Never paste the value into the UI.
- **Provider unreachable/model rejected:** verify container-to-provider routing, model name, provider `/v1` compatibility, TLS trust, and the provider's own logs. The UI returns only a sanitized outcome.
- **Context changed:** rebuild and review the exact preview; the digest intentionally prevents running stale context.
- **Advice-only result:** the provider lacks structured output or returned invalid structure. Copy is allowed; field-specific draft actions remain disabled.
- **Timeout/cancelled:** retry only after checking provider load and configured bounds. Every retry is a new, user-initiated run.

## Disable immediately

Set the kill switch to false and restart the API:

```dotenv
CCM_INFERENCE_ENABLED=false
```

```powershell
docker compose up -d --build api web
```

All ordinary compliance workflows remain available. Existing provider profiles and run history remain inert; no run can start while the switch is off. Remove the environment secret separately if it should no longer exist on the host.

Use [`field-test-checklist.md`](field-test-checklist.md) for a bounded evaluation.
