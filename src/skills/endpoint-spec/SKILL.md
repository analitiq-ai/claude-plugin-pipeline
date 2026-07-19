---
name: endpoint-spec
description: Database endpoint authoring vocabulary — database_object identity, columns with native_type and Arrow type, primary_keys. Loaded by private-endpoint-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# endpoint-spec

This skill is loaded by `private-endpoint-creator` when authoring a
database endpoint document conforming to the published database-endpoint
contract (`analitiq.contracts.endpoints.DatabaseEndpointDoc`).

## Required reading (load on demand)

- `spec-database-object.md` — catalog/schema/name/object_type rules; no
  identifier normalization.
- `spec-columns.md` — `name`, `native_type` (required), `arrow_type`
  (required, fully-qualified Apache Arrow canonical type), `nullable`,
  `default`, `comment`, `ordinal_position`.
- At least one of `examples/*.example.json` for the database dialect
  you're authoring.

## Scope

API endpoints come from the connector document, not from here. This
skill is **database-only**. API endpoints in stream `endpoint_ref`s use
`scope: connector` and point at the connector's `definition/endpoints/`.
Database endpoints use `scope: connection` and live under
`connections/<connection-slug>/definition/endpoints/`.

## What this skill covers

- The structural identity of a database object: catalog, schema, name,
  object_type. Identifier strings stored **verbatim** from
  introspection — no case-folding, quoting, or normalization.
- The column shape per table/view/collection.
- Primary keys: optional declared list, must reference existing columns.

## What this skill does NOT cover

- The connection that owns this endpoint — see `connection-spec`.
- Stream-level concerns (filters, replication, pagination, mapping) —
  those belong to `stream-spec`.
- Discovery mechanics (how to query `information_schema` etc.) — that's
  agent logic, encoded in `private-endpoint-creator`.

## Output rules

Every authored document must:

1. Declare `$schema` with the database-endpoint URL from the table below (the
   schema marks it a `const`-required field).
2. Include `endpoint_id`, `database_object`, `columns` (non-empty), and
   `$schema` — the top-level fields `DatabaseEndpointDoc` requires.
   `endpoint_id` is the **derived** handle computed by `scripts/endpoint_id.py`,
   never a hand-authored slug — see `spec-database-object.md`
   §Derived `endpoint_id`.
3. Preserve identifier strings verbatim from introspection.
4. Pass validation (the `pipeline-schema-validator`, entity `database_endpoint`)
   with zero error findings — the validator recomputes and enforces the derived
   `endpoint_id`.

<!-- BEGIN GENERATED: schema-urls -->
| Entity | Authored file | `$schema` value |
|---|---|---|
| Pipeline | `pipelines/<slug>/pipeline.json` | `https://schemas.analitiq.ai/pipeline/latest.json` |
| Stream | `pipelines/<slug>/streams/<stream-slug>.json` | `https://schemas.analitiq.ai/stream/latest.json` |
| Connection | `connections/<slug>/connection.json` | `https://schemas.analitiq.ai/connection/latest.json` |
| Database endpoint | `connections/<slug>/definition/endpoints/<endpoint_id>.json` | `https://schemas.analitiq.ai/database-endpoint/latest.json` |
<!-- END GENERATED: schema-urls -->
