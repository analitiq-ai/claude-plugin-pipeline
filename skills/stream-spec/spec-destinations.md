# `destinations` block

```jsonc
{
  "destinations": [
    {
      "endpoint_ref": { /* see spec-endpoint-refs.md */ },
      "write": {
        "mode": "insert" | "upsert" | "<api write mode>",
        "conflict_keys": ["id"]                    // required for a database upsert; forbidden for insert and for API destinations
      },
      "execution": {                              // optional; per-destination override of pipeline.runtime.batching
        "batch_size": 1000,                       // range [1, 100000]
        "max_concurrent_batches": 3               // range [1, 100]
      }
    }
  ]
}
```

`destinations` is a non-empty array. Keep each entry's `endpoint_ref` distinct
within the stream (the published schema does not declare `uniqueItems`).

## `write.mode`

| Destination kind | allowed values |
|---|---|
| database (scope=connection) | `insert`, `upsert` |
| API (scope=connector) | one of the endpoint's `operations.write` keys (e.g. `create`, `update`, `upsert`) — taken verbatim |

The orchestrator's `WriteModeMapper` (see
`../pipeline-builder/references/enum-mappers.md`) classifies the user's
intent to one of these.

## `write.conflict_keys`

**Required for a database `upsert`; forbidden for a database `insert` and for
every API (`scope: connector`) destination** (an API destination's conflict key
is endpoint-owned). The `StreamDestination` contract model enforces this — it
knows the destination scope. Shape — a **single composite key set**, a non-empty
array of destination field names:

```jsonc
["id"]                       // or ["org_id", "external_id"] for a composite key
```

Multiple alternative key sets are out of scope in the current contract. Every key
field must exist in the destination endpoint's schema; that is resolved
server-side at save time, not by the local validator.

## `execution` (per-destination override)

When present, **overrides** the pipeline-level
`runtime.batching.{batch_size,max_concurrent_batches}` for *this*
destination only. Use sparingly — pipeline defaults exist for a reason.

Typical use: a low-throughput destination next to a high-throughput one
in the same `destinations[]`.
