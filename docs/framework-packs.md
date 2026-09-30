# Framework packs

Framework packs make the external catalog replaceable while keeping assessments, controls, and evidence in the workspace layer.

## Directory contract

```text
framework-packs/<slug>/
├── manifest.yaml
├── domains.yaml
├── requirements.yaml
└── README.md
```

The combined data must satisfy [`../framework-packs/schema/framework-pack.schema.json`](../framework-packs/schema/framework-pack.schema.json).

`manifest.yaml` supplies the stable framework slug, human name, version, description, authoritative source URI, verification/publication dates, and disclaimer. Domains and requirements use external identifiers only inside the pack; the importer resolves them to internal UUIDs.

Requirements support a domain, optional parent requirement, title, concise summary, illustrative guidance, source reference, and sort order. Do not add framework-specific database columns or condition application behavior on a slug such as `soc2`.

## Authoring rules

- Use concise, original summaries; do not copy licensed standards text unless redistribution rights are explicit.
- Distinguish a source requirement from illustrative implementation practices.
- Verify every identifier, hierarchy, version, source URI, and publication date against an authoritative source.
- Include a precise disclaimer and document the verification date.
- Treat `(slug, version, content hash)` as immutable. Publish corrections as a new version.
- Never infer readiness through a crosswalk. `EQUIVALENT`, `STRONG_OVERLAP`, `PARTIAL_OVERLAP`, and `RELATED` describe coverage relationships only.

V1 automatically installs the included `soc2` pack at startup. The database and importer support multiple concurrent framework versions; a pack-management UI is future work.
