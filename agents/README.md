# Bounded agent profiles

This directory contains declarative, startup-validated profiles for optional model-assisted workflows. The field-test runtime loads only installed profiles and never stores provider credential values.

An `agent.json` describes a bounded assistant: which installed skills and read-only tools it may request, which workspace record types it may read, and which actions require human confirmation. The shape is documented in [`schema/agent-profile.schema.json`](schema/agent-profile.schema.json).

Design rules:

- Agent output is advice or a proposed change, never proof of compliance.
- Requirement status, control status, and evidence coverage remain distinct.
- A record reference is context, not authorization. Every tool call must repeat normal role and workspace checks.
- Writes, file downloads, exports, and external data transfer require explicit policy and user confirmation.
- Provider credentials belong in environment variables or a dedicated secret store. Profiles contain references only.
- A bounded iteration count, request timeout, audit event, and kill switch are mandatory before runtime enablement.

Keep profiles versioned and reviewable. Do not put prompts, tokens, passwords, evidence content, or customer data directly in a profile.
