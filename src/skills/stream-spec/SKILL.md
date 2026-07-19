---
name: stream-spec
description: Stream authoring vocabulary — endpoint refs, source filters/replication/pagination, destinations write modes, mapping assignments, validation rules. Loaded by stream-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# stream-spec

This skill is loaded by `stream-creator` when authoring a stream
document conforming to `https://schemas.analitiq.ai/stream/latest.json`.

## Required reading (load on demand)

- `spec-endpoint-refs.md` — scope=connector vs scope=connection rules.
- `spec-source.md` — selected_columns, filters, replication, database_pagination, primary_keys.
- `spec-destinations.md` — write modes, conflict_keys, execution overrides.
- `spec-mapping.md` — assignments shape; what the registry computes.
- `spec-validation-rules.md` — assignment-level validation.
- `spec-filter-operators.md` — DB vs API operator vocabularies.
- At least one of `examples/*.example.json` for the source/destination kind you're authoring.

## What this skill covers

- Top-level shape: `$schema`, `stream_id`, `display_name`, `description`,
  `pipeline_id`, `source`, `destinations`, `mapping`, `status`, `tags`.
- The mapping expression vocabulary: `{op: "get", path}` (the default) plus
  `pipe`/`fn` conversion chains, and `{arrow_type, value}` constants.
  `arrow_type` is a fully-qualified Apache Arrow canonical type string (see
  `spec-mapping.md`).
- The closed source-filter operator vocabularies per endpoint kind.

## What this skill does NOT cover

- The full registry-side type vocabulary expansion. Authored mapping
  declares one assignment per destination field; the registry computes
  `source_to_generic` / `generic_to_destination` / hashes.
- Endpoint bodies. The stream **references** endpoints by ref; it does
  not embed them.

## Cross-field rules the contract enforces

These are the relational constraints no single field can express. The validator
emits each one's stable id in the finding message, so a failure like
`[ADV-STRM-011] …` points straight at the rule below.

<!-- BEGIN GENERATED: advisory-stream -->
| Rule | Constraint |
|---|---|
| `ADV-STRM-001` | destinations must be unique by (endpoint_ref.scope, endpoint_ref.connection_id, endpoint_ref.endpoint_id). |
| `ADV-STRM-002` | mapping.assignments[].target.path must be unique within the mapping. |
| `ADV-STRM-003` | A supplied endpoint_id must equal derive_db_endpoint_id(database_object). |
| `ADV-STRM-004` | A unary filter operator (is_null/is_not_null) must omit value; every other operator requires it. |
| `ADV-STRM-005` | A pipe expression must start with a get step and be followed only by fn steps. |
| `ADV-STRM-006` | An arrow field's arrow_type must match its container shape: Object declares properties, List declares items, scalars neither. |
| `ADV-STRM-007` | constant.value's JSON kind must match arrow_type, and the Object/List/scalar container shape rule applies. |
| `ADV-STRM-008` | An assignment value must declare exactly one of expression or constant. |
| `ADV-STRM-009` | A validation rule requires value for value-taking types and omits it for required/not_null. |
| `ADV-STRM-010` | An assignment target's arrow_type must match its container shape: Object declares properties, List declares items, scalars neither. |
| `ADV-STRM-011` | conflict_keys is required for a connection-scope upsert destination and forbidden for a connector-scope or non-upsert destination. |
| `ADV-STRM-012` | A filter operator must belong to the source scope's vocabulary: the database operator set for a connection source, the API operator set for a connector source. |
| `ADV-STRM-013` | A database (connection-scope) destination's write.mode must be one of {insert, upsert}; an API (connector-scope) destination's mode is an endpoint-declared operations.write key. |
<!-- END GENERATED: advisory-stream -->

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/stream/latest.json"`.
2. Include `pipeline_id`, `source`, and a non-empty `destinations[]`
   (the schema-required fields). Author `stream_id` as an RFC-4122 UUID
   the plugin generates (plugin convention; schema permits omission and
   the service will assign one on ingest). `pipeline_id` carries the
   parent pipeline's UUID.
3. Use **connection UUIDs** in every `endpoint_ref.connection_id` — they
   must match the `connection_id` of the corresponding connection
   document.
4. Shape each `endpoint_ref` by its `scope` (see `spec-endpoint-refs.md`): a
   `connector` ref carries `endpoint_id` (the connector endpoint key); a
   `connection` ref carries the endpoint's `database_object` plus the derived
   `endpoint_id` handle.
5. Pass validation (the `pipeline-schema-validator`, entity `stream`) with zero
   error findings.
