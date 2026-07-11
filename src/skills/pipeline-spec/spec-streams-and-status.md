# `streams` and `status`

## `streams`

An array of **stream UUIDs**. Each entry is the `stream_id` of a stream
defined in a sibling `streams/<stream-slug>.json` file.

```jsonc
{
  "streams": [
    "22222222-2222-4222-8222-222222222222",
    "23232323-2323-4323-8323-232323232323"
  ]
}
```

Rules:

- UUIDs are unique within the array (`uniqueItems: true` in the schema).
- Each referenced stream's `pipeline_id` must equal this pipeline's
  `pipeline_id`. The bundle referential checks enforce this when
  `--bundle-root` is supplied.
- An empty `streams` array is permitted in `draft` or `inactive`
  status. Only `status: active` requires non-empty `streams` (see the
  status rules below).

## `status`

| value | semantics |
|---|---|
| `draft` (default) | Editable. Not scheduled. `streams` may be empty. |
| `active` | Scheduled (subject to `schedule.type`). Requires non-empty `streams` AND at least one referenced stream with its own `status: "active"`. |
| `inactive` | Paused. Not scheduled. `streams` may be empty. |

`status: active` requires runnable streams. Run with `--bundle-root`, the bundle
referential checks error when an `active` pipeline has no streams (or when no
referenced stream is itself `active`). A **draft** pipeline is legitimately not
yet runnable, so runnability is not checked for a draft (`require_runnable=False`);
it is enforced only once the pipeline is `active`.

## Authoring sequence

The orchestrator authors the pipeline shell with `streams: []` in phase
6, then stitches the stream UUIDs back in phase 8 after the parallel
`stream-creator` dispatch returns each new `stream_id`. The shell starts
in `status: draft`. Promotion to `active` happens later (typically when
the user submits the pipeline to the registry).
