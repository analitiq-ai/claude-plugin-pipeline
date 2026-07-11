# Changelog

## [unreleased]

### Changed
- Bumped the consumed contract to `analitiq-validator==1.0.0rc4`
  (`analitiq-contract-models==1.0.0rc4` transitively). Draft pipeline bundles now
  validate with `require_runnable=False`, so a not-yet-runnable draft produces no
  finding (runnability is enforced only once the pipeline is `active`); documented
  the `sidecar:` `secret_refs` scheme.
- Replaced the bundled `scripts/validate_pipeline.py` with a thin adapter
  (`src/scripts/validate.py`) over the published, offline `analitiq-validator` +
  `analitiq-contract-models` packages; it self-installs the pinned version into a
  managed virtualenv on first use. Added `src/scripts/endpoint_id.py` for the
  derived database-endpoint identity.
- Aligned all authoring to the current published contracts: connection
  `parameters`/`selections`/`secret_refs` (secrets as `env:` pointers, no
  `values` envelope); stream discriminated `endpoint_ref` carrying
  `database_object`, flat `conflict_keys`, and the `get`/`pipe`/`fn` expression
  grammar; database-endpoint derived `endpoint_id`.
- Moved the plugin package (`.claude-plugin/`, `agents/`, `skills/`, `scripts/`)
  under `src/`, separating it from repo-management files.

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
