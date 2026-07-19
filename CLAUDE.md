# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This repository is the `analitiq-pipeline-builder` Claude Code plugin: a **local authoring tool for creating and editing pipelines and streams** that move data between Analitiq DIP connectors. It authors **pipeline**, **stream**, **connection**, and **database-endpoint** JSON documents conforming to the published Analitiq schema contract at `schemas.analitiq.ai`, downloads pre-defined connectors from the DIP registry, and wires them into complete pipelines. It calls **no** registration APIs and it does **not** create connectors.

Connectors are the building blocks this plugin wires together — it never authors them:

- **Published in the DIP registry** — one repository per connector under the `analitiq-dip-registry` GitHub org: <https://github.com/orgs/analitiq-dip-registry/repositories>. `registry-browser` downloads them read-only.
- **Authored by a separate plugin** — the Analitiq connector-creator plugin (`analitiq-connector-builder`), which lives in its own repository: <https://github.com/analitiq-ai/claude-plugin-connector>.

This repository lives at <https://github.com/analitiq-ai/claude-plugin-pipeline> (public). The plugin is installed via `.claude-plugin/plugin.json`.

## Design Principles

- **Contract-first.** Every authored document — pipeline, stream, connection, database-endpoint — is written against the published JSON Schemas at `schemas.analitiq.ai`. The schema is the spec. Never invent shapes the contract doesn't define; if the contract can't express something a pipeline needs, that's a contract gap to raise, not a freeform workaround.
- **Declarative-first, author no code.** The plugin emits declarative JSON that the Analitiq engine runs. Connector behavior — including anything quirky about a source or destination system — belongs to the connector package in the DIP registry, never to a pipeline or stream.
- **Secrets are referenced, never embedded.** Connection secrets are authored as `secret_refs` pointers (`env:…` by default) and templated into a gitignored `.secrets/credentials.json`; the user (or CI) resolves them before submission. The plugin never holds, logs, or ships a secret value. (See "Connection secrets workflow" under Key Concepts.)
- **Deterministic, idempotent, no legacy.** Authored artifacts are reproducible and safe to re-run. No backward-compatibility or legacy shims unless explicitly instructed.
- **Stay in your lane.** This plugin authors pipelines / streams / connections / endpoints only. Connector documents come from the registry; creating them belongs to the connector-creator plugin. Agents must never author JSON that belongs to another agent's responsibility.

## Agents

**Agent chain:** `pipeline-builder` (skill, orchestrator) → `pipeline-provider-researcher` → `registry-browser` → `connection-creator` → `private-endpoint-creator` (DB only) → `pipeline-creator` → `stream-creator` (one per endpoint, parallel) → `pipeline-schema-validator` (loop) → `pipeline-drift-classifier`

- `pipeline-builder` (skill) — orchestrator. Collects intent, dispatches the creators, runs the validator loop, writes files only when every artifact passes. In **edit** mode it changes an existing artifact in place (surgical, non-destructive) instead of building from scratch. Loads the cross-cutting references it owns; dispatches the entity creators below.
- `pipeline-provider-researcher` — collects `PipelineFacts` (replication method, write mode, schedule, naming) from the user. No WebSearch.
- `registry-browser` — downloads the source + destination connectors from the DIP registry (read-only; reuses connectors already on disk).
- `connection-creator` — authors a `connection.json` per side (routing each contract input into `parameters` / `selections` / `secret_refs` by its `storage`) plus a sibling `.secrets/credentials.json` template the user fills in.
- `private-endpoint-creator` — database connections only: introspects the live database to discover schemas/tables and authors `database-endpoint` documents per selected table.
- `pipeline-creator` — authors the `pipeline.json` shell that references the connections by their `connection_id` UUIDs.
- `stream-creator` — authors one `stream.json` per selected endpoint (source → destination + field mapping), dispatched in parallel.
- `pipeline-schema-validator` — validates authored documents against the published contract by running the plugin's adapter (`src/scripts/validate.py`), which consumes the published `analitiq-validator` package. Returns a `Diagnostics` JSON object.
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

Authored documents declare `$schema` with the `schemas.analitiq.ai` host — the URL is locked by a `const` inside each schema. Validation itself is offline and model-driven (the `analitiq-validator` package), so no schema is fetched.

## Key Concepts

- **Identity model — UUIDs inside, slugs on disk.** The plugin authors RFC-4122 **UUIDs** for `pipeline_id`, `stream_id`, and `connection_id` and threads them through every cross-document reference. `connector_id` and `endpoint_id` are **slugs** (the connector's registry slug; the endpoint's stable `^[a-z0-9][a-z0-9_-]*$` identifier). On-disk directory names are human-readable slugs, independent of the UUID identity stored inside each document. The plugin makes no API calls; the registry can also assign UUIDs on ingest if the plugin omits them.
- **Connection secrets workflow.** A connection document has four maps — `parameters`, `selections`, `discovered`, `secret_refs` — and the plugin routes each connector-contract input/output into one by its `storage` (`connection.parameters` → `parameters`, `secrets` → `secret_refs`, `connection.selections` → `selections`; `discovered` is server-managed and never authored). For each secret, the plugin writes a pointer into `secret_refs` (`env:ANALITIQ_<slug>_<key>` by default; `file:`, `sidecar:`, `ssm:/`, `s3://`, and `arn:…` are also accepted) and emits a `.secrets/credentials.json` template keyed by the env-var names for the user to fill in. The plugin never writes a secret value into the document. `.secrets/` is gitignored and never overwritten by the orchestrator.
- **Reuse of existing artifacts.** Adding a pipeline to systems already wired up is common: an on-disk `connectors/<slug>/definition/connector.json` is reused (no re-fetch); a `connections/<slug>/connection.json` whose `connector_id` matches the side is reused as-is (including its `.secrets/`); already-discovered endpoint files are reused (only newly selected tables run introspection). A `connector_id` mismatch halts and asks the user to choose another slug or remove the file themselves.
- **Per-build vs shared state.** The only directory that blocks the orchestrator is `pipelines/<pipeline-slug>/` — if it exists, the user is asked to pick a different `pipeline_slug` or remove it themselves. The orchestrator never deletes files on the user's behalf and never overwrites a connection's `.secrets/`.

## Validation

The plugin does not ship a validator — it consumes the published, offline `analitiq-validator` + `analitiq-contract-models` packages through a thin adapter, `src/scripts/validate.py`, which normalizes every result into one `Diagnostics` JSON object (`{passed, findings[]}`). Dispatch per entity:

- `database_endpoint` → `analitiq.validator.validate_document` (contract model + the derived-`endpoint_id` gate + column checks).
- `connection` / `stream` / `pipeline` → the matching `*Input` Pydantic model (`ConnectionInput` / `StreamInput` / `PipelineInput`) — the source of truth the published JSON Schemas render from.
- `pipeline` with `--bundle-root` → additionally `analitiq.validator.validate_pipeline_bundle` for cross-document referential integrity (stream↔pipeline parentage, connection role wiring, endpoint-ref resolution). A draft pipeline is not yet runnable by design, so the adapter passes `require_runnable=False` for drafts (no not-runnable finding is produced); runnability is enforced only once the pipeline is `active`.

The adapter adds one check of its own on top of the published bundle, and only because the published contract structurally cannot make it. `validate_pipeline_bundle` receives connector **identity** only (slugs), never connector endpoint **contents**, so it leaves `scope: "connector"` endpoint refs unresolved by design. This plugin has the downloaded connector endpoint files on disk, so with `--bundle-root` it verifies each `scope: "connector"` stream ref against the connector's on-disk endpoint set (`connectors/<slug>/definition/endpoints/*.json`) and emits a **warning-only** `connector-endpoint-ref` finding — with a closest-match alignment suggestion — when the referenced endpoint is absent. It never errors (connectors are trusted registry artifacts, pinned by `connector_version` at runtime) and never edits the connector; the orchestrator aligns the stream's `endpoint_ref` instead, only on the user's confirmation.

The adapter self-installs the pinned validator (`analitiq-validator==1.0.0rc6`, see `requirements-dev.txt` / `src/scripts/_analitiq.py`) into a managed virtualenv on first use and is offline thereafter. `src/scripts/endpoint_id.py` reuses the same package to compute the derived database-endpoint identity. Run directly:

```bash
python3 src/scripts/validate.py --entity pipeline --document path/to/pipeline.json --bundle-root path/to/project
```

Output is a single `Diagnostics` JSON object. Exit `0` iff `passed: true`. Tests live under `tests/`; run with `pip install -r requirements-dev.txt && pytest`.

## File Output

```
connectors/                         # downloaded by registry-browser, read-only
└── <slug>/definition/connector.json (+ definition/endpoints/ for API connectors)

connections/
└── <connection-slug>/
    ├── connection.json             # validates against connection/latest.json
    ├── .secrets/credentials.json   # template the user fills in (gitignored)
    └── definition/endpoints/<endpoint_id>.json   # database connections only; <endpoint_id> is the derived handle

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

## GitHub

- **This repo** (public): <https://github.com/analitiq-ai/claude-plugin-pipeline>
- **DIP registry** — the connectors this plugin wires together, one repo per connector: <https://github.com/orgs/analitiq-dip-registry/repositories>
- **Connector-creator plugin** — authors those connectors (separate concern, separate repo): <https://github.com/analitiq-ai/claude-plugin-connector>
- **Analitiq Infra:** <https://github.com/analitiq-ai/analitiq-infra>
- **Analitiq Engine:** <https://github.com/analitiq-ai/analitiq-engine>

## Published Schema Contracts

Every authored document declares `$schema` against the `schemas.analitiq.ai` host:

- <https://schemas.analitiq.ai/pipeline/latest.json>
- <https://schemas.analitiq.ai/stream/latest.json>
- <https://schemas.analitiq.ai/connection/latest.json>
- <https://schemas.analitiq.ai/database-endpoint/latest.json>
- <https://schemas.analitiq.ai/api-endpoint/latest.json> — not authored; comes from the connector document
- <https://schemas.analitiq.ai/connector/latest.json> — not authored; owned by the connector-creator plugin

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
