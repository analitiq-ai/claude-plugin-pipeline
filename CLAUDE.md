# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This repository is the `analitiq-pipeline-builder` Claude Code plugin: it authors **pipeline**, **stream**, **connection**, and **database-endpoint** JSON documents conforming to the published Analitiq schema contract at `schemas.analitiq.ai`. It downloads pre-defined connectors from the DIP registry (`analitiq-dip-registry` GitHub org) and wires them into complete pipelines. It is a **local authoring tool only** — it does **not** create connectors and calls **no** registration APIs. The plugin is installed via `.claude-plugin/plugin.json`.

Creating connectors is a separate concern owned by the `analitiq-connector-builder` plugin, which lives in its own repository: [analitiq-ai/claude-plugin-connector-creator](https://github.com/analitiq-ai/claude-plugin-connector-creator).

## Agents

**Agent chain:** `pipeline-builder` (skill, orchestrator) → `pipeline-provider-researcher` → `registry-browser` → `connection-creator` → `private-endpoint-creator` (DB only) → `pipeline-creator` → `stream-creator` (one per endpoint, parallel) → `pipeline-schema-validator` (loop) → `pipeline-drift-classifier`

- `pipeline-builder` (skill) — orchestrator. Collects intent, dispatches the creators, runs the validator loop, writes files only when every artifact passes. Loads the cross-cutting references it owns; dispatches the entity creators below.
- `pipeline-provider-researcher` — collects `PipelineFacts` (replication method, write mode, schedule, naming) from the user. No WebSearch.
- `registry-browser` — downloads the source + destination connectors from the DIP registry (read-only; reuses connectors already on disk).
- `connection-creator` — authors a `connection.json` per side (single `values` envelope) plus a sibling `.secrets/credentials.json` template the user fills in.
- `private-endpoint-creator` — database connections only: introspects the live database to discover schemas/tables and authors `database-endpoint` documents per selected table.
- `pipeline-creator` — authors the `pipeline.json` shell that references the connections by their `connection_id` UUIDs.
- `stream-creator` — authors one `stream.json` per selected endpoint (source → destination + field mapping), dispatched in parallel.
- `pipeline-schema-validator` — runs Layer 1 (Draft 2020-12 JSON Schema) and Layer 2 semantic validators. Backed by `scripts/validate_pipeline.py`.
- `pipeline-drift-classifier` — surfaces the structural diff against a previous release.

Each entity creator owns its authoring vocabulary via a dedicated spec skill: `pipeline-spec`, `stream-spec`, `connection-spec`, `endpoint-spec`.

## Entities + Schemas

| Entity | Schema | Authored by |
|---|---|---|
| Pipeline | `https://schemas.analitiq.ai/pipeline/latest.json` | `pipeline-creator` |
| Stream | `https://schemas.analitiq.ai/stream/latest.json` | `stream-creator` |
| Connection | `https://schemas.analitiq.ai/connection/latest.json` | `connection-creator` |
| Database endpoint (private) | `https://schemas.analitiq.ai/database-endpoint/latest.json` | `private-endpoint-creator` |
| API endpoint | `https://schemas.analitiq.ai/api-endpoint/latest.json` | not authored — comes from the connector document |
| Connector | `https://schemas.analitiq.ai/connector/latest.json` | not authored — owned by `analitiq-connector-builder` (separate repo) |

Authored documents declare `$schema` with the `schemas.analitiq.ai` host — the URL is locked by a `const` inside each schema, and the validator fetches from the same host.

## Key Concepts

- **Identity model — UUIDs inside, slugs on disk.** The plugin authors RFC-4122 **UUIDs** for `pipeline_id`, `stream_id`, and `connection_id` and threads them through every cross-document reference. `connector_id` and `endpoint_id` are **slugs** (the connector's registry slug; the endpoint's stable `^[a-z0-9][a-z0-9_-]*$` identifier). On-disk directory names are human-readable slugs, independent of the UUID identity stored inside each document. The plugin makes no API calls; the registry can also assign UUIDs on ingest if the plugin omits them.
- **Connection secrets workflow.** Connection documents use a single flat `values` envelope. For inputs whose connector-contract bucket is `secrets`, the plugin writes a human-readable placeholder (`"<see .secrets/credentials.json>"`) into `values` and emits a `.secrets/credentials.json` template the user fills in. The user (or CI) merges secret values into the document's `values` block before submitting the connection to the registry. The registry never reads `.secrets/` directly. `.secrets/` is gitignored and never overwritten by the orchestrator.
- **Reuse of existing artifacts.** Adding a pipeline to systems already wired up is common: an on-disk `connectors/<slug>/definition/connector.json` is reused (no re-fetch); a `connections/<slug>/connection.json` whose `connector_id` matches the side is reused as-is (including its `.secrets/`); already-discovered endpoint files are reused (only newly selected tables run introspection). A `connector_id` mismatch halts and asks the user to choose another slug or remove the file themselves.
- **Per-build vs shared state.** The only directory that blocks the orchestrator is `pipelines/<pipeline-slug>/` — if it exists, the user is asked to pick a different `pipeline_slug` or remove it themselves. The orchestrator never deletes files on the user's behalf and never overwrites a connection's `.secrets/`.

## Validation

`scripts/validate_pipeline.py` runs Layer 1 (Draft 2020-12 JSON Schema, against the schema selected by `--entity {pipeline|stream|connection|database_endpoint}`) plus Layer 2 semantic validators:

- `reserved-field` — no server-managed fields in authored docs.
- `schedule-shape` — manual / interval / cron field exclusivity; IANA timezone parses.
- `runtime-ranges` — engine vcpu/memory, runtime buffer/batching, error-handling retries.
- `endpoint-ref-shape` — `scope ∈ {connector, connection}` (`connection` reserved for database endpoints); destination refs unique.
- `mapping-shape` — exactly one of `expression` / `constant` per assignment; `expression.op == "get"` (v1); unique target paths; validation rules reference mapped fields.
- `filter-operators` — database vs API operator vocabularies; unary operators omit `value`.
- `column-uniqueness` — column-name and `ordinal_position` uniqueness; primary-key resolution against declared columns.
- `pipeline-stream-consistency` (with `--bundle-root`) — every referenced stream's `pipeline_id` matches the parent pipeline; endpoint-ref connection IDs are members of `pipeline.connections`.
- `status-lifecycle` — `status=active` requires runnable streams.

Run directly:

```bash
python scripts/validate_pipeline.py --entity pipeline --document path/to/pipeline.json --bundle-root path/to/project
```

Output is a single `Diagnostics` JSON object. Exit `0` iff `passed: true`. Tests live under `tests/pipeline_validator/`; run with `pytest`.

## File Output

```
connectors/                         # downloaded by registry-browser, read-only
└── <slug>/definition/connector.json (+ endpoints/ for API connectors)

connections/
└── <connection-slug>/
    ├── connection.json             # validates against connection/latest.json
    ├── .secrets/credentials.json   # template the user fills in (gitignored)
    └── endpoints/<endpoint-slug>.json   # database connections only

pipelines/
└── <pipeline-slug>/
    ├── pipeline.json               # validates against pipeline/latest.json
    └── streams/<stream-slug>.json  # validates against stream/latest.json
```

## Versioning

The plugin's package version in `.claude-plugin/plugin.json` is bumped on PR merge via labels (`version:minor`, `version:patch`, `version:major`) — never bump it manually. `pipeline-drift-classifier` surfaces the structural diff between an authored bundle and a previous release.

## Conventions

- JSON Schema Draft 2020-12 throughout.
- UUIDs for `pipeline_id` / `stream_id` / `connection_id`; slugs for `connector_id` / `endpoint_id` and all on-disk directory names.
- Test org_id: `d7a11991-2795-49d1-a858-c7e58ee5ecc6`.
- Agents must never author JSON that belongs to another agent's responsibility.
- The orchestrator never deletes or overwrites user files (especially `.secrets/`); it halts and asks instead.

## PR Review Process

After creating a PR, follow these steps. Continue invoking the PR review process until no more errors are raised. If raised errors are not relevant to the PR, ask if you should create a GitHub issue for the raised error.

1. Use `/pr-review-toolkit` to review the PR after implementing all changes.
2. Wait for feedback from the review executor.
3. Determine if the raised issues are legitimate or not.
   a. if legitimate and relevant to the PR, fix it.
   b. if outside the scope of the PR, check for a related GitHub issue; if none, create one and move on.
   c. if not a legitimate problem, summarize your reasoning and move on.
4. Once fixed, commit and push to the branch.
5. Use `/pr-review-toolkit` to review again.
6. Repeat until the PR is approved.
7. Once approved, run the tests to make sure they all pass.
