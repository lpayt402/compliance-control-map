# Bounded skill manifests

Skills are small, reviewable instructions for optional model assistance—for example, drafting implementation notes from user-selected records. The field-test runtime discovers only installed, valid manifests.

[`schema/skill-manifest.schema.json`](schema/skill-manifest.schema.json) defines the manifest shape. The loader accepts only installed, schema-valid manifests, resolves referenced files beneath the skill directory, and rejects traversal, escaping symlinks, undeclared tools, writable behavior, invalid limits, and unsupported scopes.

Skills do not bypass the API. Reads and writes still pass through the same workspace, role, validation, concurrency, and activity-log boundaries as manual actions. A skill may propose a readiness change; it may not infer or transfer compliance status automatically.
