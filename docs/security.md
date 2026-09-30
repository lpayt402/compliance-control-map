# Security posture and deployment checklist

This is an MVP security baseline, not a penetration test, certification, or promise that an internet-facing deployment is secure. Local mode is intentionally loopback-only. Team mode should sit behind a maintained TLS reverse proxy and a trusted network boundary.

## Current review snapshot — 2026-08-21

The current verification ceiling for this type of application is [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/) at roughly Level 2, interpreted with [NIST SP 800-228 update 1](https://csrc.nist.gov/pubs/sp/800/228/upd1/final) for API lifecycle controls and [NIST SP 800-63B-4](https://csrc.nist.gov/pubs/sp/800/63/b/4/final) for authentication. Recent exploited-vulnerability patterns continue to emphasize unsafe deserialization, command injection, authentication bypass, path traversal, and unrestricted upload; use the live [CISA KEV catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) rather than a frozen list. Supply-chain practice has shifted toward short-lived OIDC/trusted publishing, full workflow pinning, install cooldowns, and registry malware scanning; GitHub summarized the credential-exfiltration pattern in April 2026 in [Securing the open source supply chain](https://github.blog/security/supply-chain-security/securing-the-open-source-supply-chain-across-github/). This review found drift in the original container pins, so the MVP now uses the August 2026 Python 3.12, Node 22, Nginx stable, and PostgreSQL 17 security releases. Application dependencies remain exact-pinned; production operators should additionally digest-pin images and scan them in their own release pipeline.

## Implemented controls

- Every business record is scoped to a workspace; route dependencies enforce Admin, Editor, and Viewer capabilities.
- Local no-auth mode is rejected for non-loopback binding unless an explicit unsafe override is set. Team mode enables login.
- Passwords require at least 15 characters and use Argon2id. Sessions are random, stored as SHA-256 token digests, expire after 12 hours, and are revoked on logout. Login attempts have an in-process throttle.
- Mutations use same-origin and synchronizer-token CSRF checks. Session and CSRF cookies are `HttpOnly`/`Secure` where applicable and use same-site restrictions.
- CORS and trusted hosts are allowlists. Safe API errors hide tracebacks and include a bounded request ID.
- SQLAlchemy parameterization is used for database access. Pydantic validates request bodies and query bounds.
- Uploads use allowlisted extensions, type/signature checks, size limits, randomized storage keys, SHA-256 digests, and storage outside the web root. Downloads are authenticated attachments.
- Export restore bounds ZIP members and expansion, rejects traversal and duplicate names, and verifies every declared file digest.
- Nginx and the API send restrictive CSP, framing, MIME sniffing, referrer, permissions, and cross-origin resource headers. Images run without root; only the web service publishes a host port.
- Important assessment, mapping, upload, owner, and note changes create activity records.
- Optional model requests are disabled by default; when enabled they use exact outbound URL allowlisting, proxy bypass, redirect refusal, DNS/address revalidation, environment-only secret resolution, bounded time/context/output/tool limits, per-run external-transfer confirmation, workspace-scoped reads, and sanitized activity.

## Deployment owner responsibilities

Before team use, replace every `CHANGE_ME` secret, set exact allowed origins/hosts, terminate TLS 1.3/1.2 at a maintained proxy, configure HSTS there, restrict the host firewall, protect and encrypt backups, patch images/dependencies, centralize logs, and test restore. Use a least-privilege PostgreSQL role and encrypted database connections when the database crosses a host boundary.

Do not expose team mode directly to the public internet without adding MFA/SSO, durable distributed rate limiting, operational alerting, a recovery plan, and an environment-specific threat model. This build does not supply a WAF/DDoS service, malware scanner, encryption-at-rest system, MFA, password reset, OIDC, PostgreSQL row-level security, SBOM pipeline, signed release pipeline, or security monitoring integration.

## Optional model-assistance boundary

Model assistance remains optional and defaults off. The application is designed to operate normally when the feature or provider is unavailable. Enabling the kill switch loads installed agent/skill definitions and permits Admin-configured OpenAI-compatible provider profiles. Credential values remain in environment variables; database/API/export records never contain them.

Every model run is explicitly initiated by an Admin or Editor after reviewing exact bounded context. Non-local providers require a fresh transfer confirmation. Server-selected records and each named read-only tool call repeat workspace/role authorization. Stored attachment bytes are excluded. Redirects, proxy-environment routing, URL credentials, traversal, unlisted bases, and metadata/link-local/multicast/unspecified destinations are blocked; DNS is rechecked when the destination is used.

Output is untrusted advice and cannot mutate workspace records. Structured proposals can prefill only local browser form state and require the normal authorized Save action. General activity includes safe identifiers and outcomes, never prompts, record context, output, secrets, tokens, provider headers/payloads, or raw errors. See [`model-assistance.md`](model-assistance.md) for configuration, limits, known constraints, and immediate disablement.

## Review checklist

For each release, verify access and object authorization, production configuration, dependency advisories, TLS/cookies, injection/upload paths, rate limits/timeouts, authentication/session behavior, archive integrity, non-secret activity logging, and fail-closed exceptions. Run the automated suites in [`../AGENTS.md`](../AGENTS.md), inspect the rendered browser application, and review dependency/container advisories before deployment.

Relevant baselines: [OWASP Top 10:2025](https://owasp.org/Top10/2025/), [OWASP API Security Top 10:2023](https://owasp.org/API-Security/editions/2023/en/0x00-header/), [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/), [NIST SP 800-63B-4](https://csrc.nist.gov/pubs/sp/800/63/b/4/final), and the [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
