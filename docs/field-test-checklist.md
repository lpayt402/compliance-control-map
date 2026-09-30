# Model-assistance field-test checklist

Record environment, browser, provider implementation/version, model ID, profile policy, tester role, and run IDs with each issue. Do not paste secrets, complete context, model output, or uploaded file contents into issue trackers.

## Setup and connectivity

- [ ] Start from a backup and confirm ordinary workflows work with `CCM_INFERENCE_ENABLED=false`.
- [ ] Enable assistance with one exact local or HTTPS base URL; confirm no wildcard or extra destination is allowed.
- [ ] Configure a profile using no secret or only an `env:NAME` reference.
- [ ] Test the provider from Settings and record only the sanitized result and request ID.
- [ ] For host Ollama, verify API-container access to `http://host.docker.internal:11434/v1/models`.

## Bounded workflows

- [ ] As an Editor, open one requirement, run Requirement Summary, and confirm streamed output cites source references.
- [ ] Run Draft Implementation Notes, use the structured proposal as a local draft, confirm the record is unchanged, then use the normal Save action.
- [ ] Run Draft Evidence-Collection Playbook, prepopulate a playbook locally, and save it manually.
- [ ] Open a mapped control, run Control Review, apply a local implementation-note draft, and save it manually.
- [ ] Confirm context options rebuild the preview and stored attachment bytes are always reported excluded.
- [ ] With a non-local provider, confirm each run requires a fresh external-transfer checkbox.
- [ ] Stop one live run and confirm the terminal state is **Cancelled**.
- [ ] Simulate a slow provider and confirm the terminal state is **Timed out**.
- [ ] Use a provider without structured output and confirm the result is advice-only, Copy remains, and field-specific draft buttons are absent.

## Roles, persistence, and feedback

- [ ] Confirm a Viewer sees no Assist tab and cannot call run/provider mutation endpoints.
- [ ] Submit Useful and Not useful ratings with and without a short comment; confirm feedback remains local.
- [ ] Create a backup and verify it restores normally and contains no secret value, secret reference, provider profile, run prompt, context, or raw model payload.
- [ ] Disable the global kill switch, restart, and confirm the application remains fully usable and runs are rejected.
- [ ] At desktop and narrow viewport sizes, confirm keyboard focus is visible and there is no page-level horizontal overflow.

## Issue record

- [ ] Expected versus actual behavior
- [ ] Sanitized run ID and request ID
- [ ] Terminal state and safe error code
- [ ] Provider/profile identifier and model ID (no credential)
- [ ] Skill/version and selected record types
- [ ] Whether typed text was included; confirm attachment bytes were excluded
- [ ] Reproduction steps and screenshot with sensitive workspace text removed
