# `endpoint_ref` shape

The `source` and every `destinations[]` entry carry an `endpoint_ref`. It is a
**discriminated union on `scope`** — the two scopes have different shapes:

## `scope: "connector"` — public connector endpoint (API)

```jsonc
{
  "scope": "connector",
  "connection_id": "<connection-uuid>",
  "endpoint_id": "<connector endpoint key>"
}
```

Refers to a public endpoint baked into the connector document (typically API
endpoints), pinned by the connection's `connector_version` at runtime. All three
fields are required. `endpoint_id` matches a key under the connector's
`definition/endpoints/*.json`.

## `scope: "connection"` — private database endpoint

```jsonc
{
  "scope": "connection",
  "connection_id": "<connection-uuid>",
  "endpoint_id": "<derived endpoint handle>",
  "database_object": { "schema": "public", "name": "orders" }
}
```

Refers to a private, connection-scoped database endpoint produced by
introspection. **`database_object` is required** and carries the verbatim
database-object identity — the same `{catalog?, schema?, name}` recorded on the
endpoint document (author it from the endpoint doc's `database_object`, i.e. the
`build_database_object(...)` output, so the two always agree). `endpoint_id` is
optional in the schema, but **author it** (the derived
`slug(schema)__slug(table)[__slug(catalog)]__<hash8>` handle) so the
cross-document bundle check can resolve the reference.

`scope: "connection"` is valid only for **database** endpoints. Connection-scoped
API endpoints await an API-endpoint snapshot-hashing spec; `stream-creator`
refuses that combination.

## `connection_id`

The **`connection_id` UUID** of the connection the parent pipeline selected for
that side — `pipeline.connections.source` for the stream source, and one of
`pipeline.connections.destinations[]` for each destination.

## Uniqueness

Destination `endpoint_ref`s must be unique within a single stream.

## Cross-document consistency

Validated with `--bundle-root` (the `bundle-*` checks): every source
`endpoint_ref.connection_id` equals `pipeline.connections.source`; every
destination `endpoint_ref.connection_id` is one of
`pipeline.connections.destinations`; and every `scope: "connection"` ref resolves
to a bundled database-endpoint document by `(connection_id, endpoint_id)`.
