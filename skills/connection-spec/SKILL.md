---
name: connection-spec
description: Connection authoring vocabulary — the parameters/selections/discovered/secret_refs envelope, storage-driven routing, and the `.secrets/` template workflow. Loaded by connection-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connection-spec

This skill is loaded by `connection-creator` when authoring a connection
document conforming to `https://schemas.analitiq.ai/connection/latest.json`.

## Required reading (load on demand)

- `spec-envelope.md` — the four author-time maps
  (`parameters`/`selections`/`discovered`/`secret_refs`), the storage-driven
  routing rule, and the `env:` secret-pointer + `.secrets/` template workflow.
- The closest `examples/*.example.json` for the connector's `auth.type` (shape
  guidance only; the connector contract's `storage` is authoritative for
  routing, so the example set never needs to grow when a new connector ships).

## What this skill covers

- Top-level shape: `$schema`, `connection_id`, `connector_id`, `display_name`,
  `description`, `parameters`, `selections`, `discovered`, `secret_refs`,
  `tags`. `connector_id` is the only schema-required field; everything else is
  optional.
- Routing each `connection_contract` input / post-auth output into its map by
  the last segment of its declared `storage` (see `spec-envelope.md`).
- Scaffolding `secret_refs` as `env:` pointers plus the matching
  `.secrets/credentials.json` template.

## What this skill does NOT cover

- The connector's `connection_contract` itself — that lives in the connector
  document, authored by the `analitiq-connector-builder` plugin.
- Endpoint discovery — see `endpoint-spec`.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/connection/latest.json"`.
2. Author `connector_id` (the connector slug being instantiated; required).
   `connection_id` is an RFC-4122 UUID — author one the plugin generates, or
   omit it and let the service assign one on ingest.
3. Route every contract input/output into `parameters` / `selections` /
   `secret_refs` by its `storage` (never author `discovered` — it is
   server-managed). For each `storage: "secrets"` key, write an `env:` pointer
   into `secret_refs` and add the env-var name to `.secrets/credentials.json`.
4. Pass the validator (`pipeline-schema-validator`, entity `connection`) with
   zero error findings.
