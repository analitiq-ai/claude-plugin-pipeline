# Schema host

All Analitiq schemas are served from a single host:
`https://schemas.analitiq.ai/`. Authored documents declare `$schema` against it —
the URL is locked by a `const` inside each published schema.

| Concern | Where |
|---|---|
| Document's `$schema` declaration | `https://schemas.analitiq.ai/` (locked by a `const` inside the schema) |
| Validation | the published `analitiq-validator` + `analitiq-contract-models` packages — **offline**, model-driven; no schema is ever fetched |

## How validation works

The plugin does **not** fetch or cache schemas. `analitiq-validator` validates
each document against the bundled Pydantic contract models — the same source of
truth the published JSON Schemas are rendered from. The
`pipeline-schema-validator` agent runs the plugin's adapter (`scripts/validate.py`),
which self-installs the pinned validator into a managed virtualenv on first use
and is offline thereafter:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" \
  --entity pipeline \
  --document path/to/pipeline.json \
  [--bundle-root .]
```

Because validation is offline, a document's declared `$schema` URL is a label,
not a fetch target — keep it in sync with the entity so the file stays
self-describing.
