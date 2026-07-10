# Reserved (server-managed) fields per entity

Authored documents must **never** contain any of these fields. The
registry stamps them on insert/update. The published contract models are the
strict *input* variants — they forbid unknown fields, so a leaked server-managed
field fails validation.

## Pipeline

- `version`
- `org_id`
- `created_at`
- `updated_at`

`pipeline_id` is **not** reserved — it is an optional authored UUID
(see `identity-and-versioning.md`).

## Stream

- `version`
- `org_id`
- `created_at`
- `updated_at`
- `schema_hash`
- `mapping.assignments_hash` (server-computed, `readOnly`; the model rejects a client-authored value)
- `source_schema_fingerprint`
- `target_schema_fingerprint`
- `source_schema_id`
- `target_schema_id`
- `source_to_generic`
- `generic_to_destination`
- `type_mapping_assignments_hash`

`stream_id` is **not** reserved — it is an optional authored UUID.
`pipeline_id` is **authored** on streams as the parent pipeline's UUID
cross-reference; it is required.

The legacy mapping fields (`source_to_generic`, `generic_to_destination`,
plus the hash fields above) are server-managed under the new schema.
Authored mapping is `assignments`-only — one entry per destination field.
The registry computes the rest.

## Connection

- `version`
- `org_id`
- `connector_version`
- `auth_state` (the auth lifecycle status block)
- `created_at`
- `updated_at`

`connection_id` is **not** reserved — it is an optional authored UUID.
`connector_id` is **authored** as the connector slug (or UUID) and is
required.

## Database endpoint

- `connector_id`
- `connector_version`
- `connection_id`
- `schema_hash`

`endpoint_id` is **authored** — the derived handle
`slug(schema)__slug(name)[__slug(catalog)]__hash8` (still matching
`^[a-z0-9][a-z0-9_-]*$`) — and is required; it serves as the catalog key after
the endpoint is materialized. See `endpoint-spec` / `scripts/endpoint_id.py`.

## Authored shape vs. persisted shape

The published JSON Schemas — and the `*Input` contract models they render from —
describe the **authored** shape (the strict input variant), which already omits
every server-managed field above. So an authored document validates without any
special handling, and authoring a server-managed field fails because the models
forbid unknown fields. The persisted, post-stamped record shape is internal and
not published.
