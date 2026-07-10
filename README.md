# Analitiq Pipeline Builder Plugin

A Claude Code plugin for **creating and running data pipelines and streams**
between [Analitiq DIP](https://github.com/orgs/analitiq-dip-registry/repositories)
connectors. Describe a source and a destination in plain language; the plugin
downloads the connectors from the registry, interviews you for the details, and
authors validated **pipeline**, **stream**, **connection**, and
**database-endpoint** JSON documents against the published schema contract at
[`schemas.analitiq.ai`](https://schemas.analitiq.ai).

It is a **local authoring tool**: it never creates connectors — that's the
[connector-creator plugin](https://github.com/analitiq-ai/claude-plugin-connector) —
and it calls no registration APIs. It only writes JSON to disk for you to review
and submit.

## Install

```bash
claude plugin add ./claude-plugin-pipeline
```

## Use

Launch Claude Code in your project and describe the pipeline you want:

> build a pipeline from Stripe to Snowflake

The plugin then:

1. **Interviews you** — replication method, write mode, schedule, naming.
2. **Downloads** the source and destination connectors from the DIP registry
   (read-only; reused if already on disk).
3. **Authors** a connection per side (with a `.secrets/credentials.json`
   template you fill in), the endpoint documents, the pipeline shell, and one
   stream per endpoint.
4. **Validates** every artifact against the published JSON Schemas plus a layer
   of semantic checks.
5. **Writes files** to disk — only once everything passes.

Output lands under `connections/`, `pipelines/`, and (read-only) `connectors/`.
Fill in the `.secrets/` templates, then submit the connections and pipeline to
the registry. The full file layout, identity model, and secrets workflow are
documented in [CLAUDE.md](CLAUDE.md).

## Validate manually

The bundled validator runs Draft 2020-12 JSON Schema plus semantic rules:

```bash
python scripts/validate_pipeline.py \
  --entity pipeline \
  --document path/to/pipeline.json \
  --bundle-root path/to/project
```

Output is a single `Diagnostics` JSON object; exit `0` iff `passed: true`.
Tests live under `tests/pipeline_validator/` — run with `pytest`. The complete
set of validators is listed in [CLAUDE.md](CLAUDE.md).

## How it fits together

This plugin **wires connectors into pipelines** — it does not build the
connectors themselves.

| | Repository | Role |
|---|---|---|
| **This plugin** | [claude-plugin-pipeline](https://github.com/analitiq-ai/claude-plugin-pipeline) | Authors pipelines, streams, connections, and endpoints. |
| Connectors | [analitiq-dip-registry](https://github.com/orgs/analitiq-dip-registry/repositories) | One repository per connector; downloaded read-only. |
| Connector-creator | [claude-plugin-connector](https://github.com/analitiq-ai/claude-plugin-connector) | Authors the connectors this plugin consumes. |
| Schemas | [schemas.analitiq.ai](https://schemas.analitiq.ai) | The published JSON Schema contract everything validates against. |

Architecture, the agent chain, and internals are documented in
[CLAUDE.md](CLAUDE.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).
