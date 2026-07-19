# `destinations` block

The accepted shape is `analitiq.contracts.stream.StreamDestination`, with
`analitiq.contracts.stream.Write` and `analitiq.contracts.stream.Execution` for
its two sub-blocks. The sketch below illustrates a filled-in destination; the
required-field and bound facts live on those models.

```jsonc
{
  "destinations": [
    {
      "endpoint_ref": { /* see spec-endpoint-refs.md */ },
      "write": {
        "mode": "upsert",
        "conflict_keys": ["id"]
      },
      "execution": {
        "batch_size": 1000,
        "max_concurrent_batches": 3
      }
    }
  ]
}
```

## Uniqueness and repeated connections

Destinations must be distinct by their endpoint ref — `ADV-STRM-001` (see
`SKILL.md` § Cross-field rules) states the tuple and the contract model enforces
it. The emitted JSON Schema carries no `uniqueItems` keyword for `destinations`,
so a schema-only reading looks permissive; it is not. Duplicates fail validation.

Because uniqueness is over the whole ref and not over `connection_id`, the **same
destination connection may legitimately appear in several destination entries**
as long as the endpoint differs — fanning one stream into two tables of the same
warehouse is a normal shape, not a duplicate.

## `write.mode`

| Destination kind | allowed values |
|---|---|
| database (scope=connection) | the closed database write-mode set — see `ADV-STRM-013` |
| API (scope=connector) | one of the endpoint's `operations.write` keys (e.g. `create`, `update`, `upsert`) — taken verbatim |

`ADV-STRM-013` is what makes `write.mode` scope-sensitive: the field's type is an
open string because an API mode is endpoint-declared, but a database destination
is narrowed to the closed set. The orchestrator's `WriteModeMapper` (see
`../pipeline-builder/references/enum-mappers.md`) classifies the user's intent to
one of these.

## `write.conflict_keys`

`ADV-STRM-011` governs when this field is required and when it is forbidden; the
`StreamDestination` model can enforce it because the destination's ref tells it
the scope. Shape — a **single composite key set**, a non-empty array of
destination field names:

```jsonc
["id"]                       // or ["org_id", "external_id"] for a composite key
```

Multiple alternative key sets are out of scope in the current contract. Every key
field must exist in the destination endpoint's schema; that is resolved
server-side at save time, not by the local validator.

## `execution` (per-destination override)

`execution` is one of **three** places batching is decided, and each has a
different owner:

| Layer | Field | Owner | Meaning |
|---|---|---|---|
| Pipeline default | `pipeline.runtime.batching` | the pipeline | the baseline for every binding |
| Stream override | destination `execution` | this stream | overrides the default for *this* `(stream, destination)` binding only |
| Provider capacity | destination endpoint `operations.write.batching` | the endpoint | how much the provider will accept in one request |

Resolution runs in that order — pipeline defaults, then the stream override, then
endpoint and runtime hard limits capping whatever the override produced. The
endpoint's `batching` is not a default and not an override: it is a ceiling
describing the provider, and no stream may raise it.

Use `execution` sparingly — pipeline defaults exist for a reason. Typical use: a
low-throughput destination next to a high-throughput one in the same
`destinations[]`.

What the two knobs mean per destination kind:

- **API destination** — the endpoint's write `batching.max_records` caps how many
  records may ride in one provider request.
- **Database destination** — `execution.batch_size` is the write chunk size once
  defaults have resolved.

If a write operation declares no `batching` at all, the runtime treats it as
single-record writes. That is a real throughput cliff on an API destination:
absent batching does not mean "unbounded", it means one record per request.
