# Inference boundary (disabled in V1)

This package reserves a provider-neutral seam for a future model-assisted workspace. It is a contract, not a feature: there is no API route, provider SDK, credential store, network client, prompt runner, or background agent in V1.

`ProviderConnection` records the information an adapter would need—endpoint, model identifier, capability flags, timeout, TLS posture, data-handling posture, and a reference to an externally managed secret. Raw API keys are deliberately not representable.

Any future implementation must keep inference advisory: model output may propose summaries or edits, but normal authorization, validation, optimistic concurrency, and explicit user confirmation remain authoritative. Record references are scoped identifiers, not permission grants. Tools and skills are allowlisted by identifier and must be authorized again at execution time.

Before enabling an adapter, add a threat model, outbound-network policy, tenant isolation tests, prompt-injection defenses, audit events, usage limits, deletion/retention rules, and provider-specific data-processing documentation.
