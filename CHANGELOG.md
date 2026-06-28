# Changelog

## [unreleased]

## [0.1.0]

### Added
- Initial release of the standalone `analitiq-pipeline-builder` plugin,
  extracted from the `analitiq-ai/ai-plugins-official` monorepo into its
  own repository. Authors pipeline, stream, connection, and
  database-endpoint JSON documents that conform to the published Analitiq
  schema contract at `schemas.analitiq.ai`. Downloads connectors from the
  DIP registry and wires them into complete pipelines; it does not create
  connectors and calls no registration APIs.
- Agent chain: `pipeline-builder` (orchestrator skill) →
  `pipeline-provider-researcher` → `registry-browser` →
  `connection-creator` → `private-endpoint-creator` (DB only) →
  `pipeline-creator` → `stream-creator` (parallel) →
  `pipeline-schema-validator` → `pipeline-drift-classifier`.
- `scripts/validate_pipeline.py` (Layer 1 JSON Schema + Layer 2 semantic
  validators) with the pytest suite under `tests/pipeline_validator/`.
