# Changelog

## [unreleased]

### Changed
- Replaced the bundled `scripts/validate_pipeline.py` with a thin adapter
  (`scripts/validate.py`) over the published, offline `analitiq-validator` +
  `analitiq-contract-models` packages; it self-installs the pinned version into a
  managed virtualenv on first use. Added `scripts/endpoint_id.py` for the derived
  database-endpoint identity.
- Aligned all authoring to the current published contracts: connection
  `parameters`/`selections`/`secret_refs` (secrets as `env:` pointers, no
  `values` envelope); stream discriminated `endpoint_ref` carrying
  `database_object`, flat `conflict_keys`, and the `get`/`pipe`/`fn` expression
  grammar; database-endpoint derived `endpoint_id`.

### Added
- Edit mode in the `pipeline-builder` orchestrator — surgical, in-place changes
  to an existing pipeline / stream / connection / database-endpoint.

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
