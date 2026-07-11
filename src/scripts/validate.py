#!/usr/bin/env python3
"""Validate an authored Analitiq document against the published contract.

This is a thin **adapter**. It holds no validation logic of its own — it
dispatches to the published `analitiq-validator` + `analitiq-contract-models`
packages (the same offline, model-driven contract the Analitiq services validate
against) and normalizes every backend into one Diagnostics envelope:

    {"passed": bool, "findings": [{"validator", "severity", "path", "message"}]}

The published package deliberately exposes three different entry points, because
one artifact kind is not like the others. This adapter routes each entity to the
right one:

  * ``database_endpoint`` -> ``analitiq.validator.validate_document`` — the model
    plus the derived-``endpoint_id`` gate and column checks (the same code the
    ``analitiq-validate`` CLI runs).
  * ``connection`` / ``stream`` / ``pipeline`` -> the matching ``*Input`` Pydantic
    model's ``.model_validate`` (the source of truth the published JSON Schemas
    are rendered from; the CLI does not recognize these single-document kinds).
  * ``pipeline`` with ``--bundle-root`` -> additionally
    ``analitiq.validator.validate_pipeline_bundle`` over the on-disk bundle, for
    the cross-document referential integrity no single document can verify.

Validation is offline — no schema is fetched. Usage::

    python3 src/scripts/validate.py --entity pipeline --document path/to/pipeline.json --bundle-root .

Exit status is ``0`` iff ``passed`` (no error-severity finding), ``1`` on any
error finding or an unreadable document, ``2`` on a CLI usage error.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _analitiq import VALIDATOR_PIN, ensure_deps_or_reexec

ENTITIES = ("pipeline", "stream", "connection", "database_endpoint")


# ---------------------------------------------------------------------------
# Finding + Diagnostics shape
# ---------------------------------------------------------------------------

def _finding(validator: str, severity: str, path: str, message: str) -> dict:
    return {"validator": validator, "severity": severity, "path": path, "message": message}


def _diagnostics(findings: list[dict]) -> dict:
    passed = all(f.get("severity") != "error" for f in findings)
    return {"passed": passed, "findings": findings}


# ---------------------------------------------------------------------------
# Per-entity validation (importable + unit-testable; analitiq imported lazily so
# importing this module never requires the validator to be installed)
# ---------------------------------------------------------------------------

def _model_findings(entity: str, doc) -> list[dict]:
    """Validate a single connection/stream/pipeline document against its published
    contract model, mapping each Pydantic error to a finding (the same mapping the
    validator itself uses internally)."""
    if entity == "connection":
        from analitiq.contracts.connection import ConnectionInput as Model
    elif entity == "stream":
        from analitiq.contracts.stream import StreamInput as Model
    elif entity == "pipeline":
        from analitiq.contracts.pipelines.config import PipelineInput as Model
    else:  # pragma: no cover - guarded by the entity choices
        raise ValueError(f"no contract model for entity {entity!r}")
    from pydantic import ValidationError
    try:
        Model.model_validate(doc)
        return []
    except ValidationError as exc:
        return [
            _finding("contract-model", "error",
                     "/" + "/".join(str(p) for p in err["loc"]), err["msg"])
            for err in exc.errors()
        ]


def _endpoint_findings(doc, document_path: Path) -> list[dict]:
    from analitiq.validator import validate_document
    return validate_document(doc, doc_path=document_path.resolve())


def _read_bundle_member(path: Path, findings: list[dict]) -> dict | None:
    """Read one sibling bundle document. On an unreadable/invalid file or a
    non-object payload, append an error finding and return None — so a malformed
    sibling becomes a clear diagnostic instead of an uncaught traceback or a
    silently dropped document."""
    try:
        doc = _read_json(path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        findings.append(_finding("document", "error", "", f"Cannot read {path.name}: {exc}"))
        return None
    if not isinstance(doc, dict):
        findings.append(_finding("document", "error", "", f"{path.name} is not a JSON object"))
        return None
    return doc


def _assemble_bundle(pipeline_doc: dict, document_path: Path, root: Path) -> tuple[dict, list[dict]]:
    """Gather the on-disk pipeline bundle the way the engine resolves it at load:
    the pipeline plus its sibling stream documents, every connection, the
    connection-scoped endpoint documents (stamped with their owning connection's
    id, which endpoint documents do not carry themselves), and the downloaded
    connector identities. Returns the bundle plus any read-error findings for
    malformed siblings."""
    findings: list[dict] = []

    streams: list[dict] = []
    for p in sorted((document_path.parent / "streams").glob("*.json")):
        doc = _read_bundle_member(p, findings)
        if doc is not None:
            streams.append(doc)

    connections: list[dict] = []
    endpoints: list[dict] = []
    for conn_json in sorted((root / "connections").glob("*/connection.json")):
        conn = _read_bundle_member(conn_json, findings)
        if conn is None:
            continue
        connections.append(conn)
        connection_id = conn.get("connection_id")
        for ep_json in sorted((conn_json.parent / "endpoints").glob("*.json")):
            endpoint = _read_bundle_member(ep_json, findings)
            if endpoint is None:
                continue
            # Endpoint documents omit connection_id (server-managed); supply the
            # owning connection's id so the bundle's endpoint-ref check can resolve
            # connection-scoped references.
            endpoint.setdefault("connection_id", connection_id)
            endpoint.setdefault("scope", "connection")
            endpoints.append(endpoint)

    # Connectors supply identity only, and the directory slug already is that
    # identity — so a malformed connector.json is best-effort skipped (its slug
    # still counts), not a bundle error.
    connectors: set[str] = set()
    for conn_json in sorted((root / "connectors").glob("*/definition/connector.json")):
        connectors.add(conn_json.parent.parent.name)  # directory slug
        try:
            cid = _read_json(conn_json).get("connector_id")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            continue
        if isinstance(cid, str) and cid:
            connectors.add(cid)

    bundle = {
        "pipeline": pipeline_doc,
        "streams": streams,
        "connections": connections,
        "connectors": sorted(connectors),
        "endpoints": endpoints,
    }
    return bundle, findings


def _bundle_findings(pipeline_doc: dict, document_path: Path, root: Path) -> list[dict]:
    from analitiq.validator import validate_pipeline_bundle
    bundle, findings = _assemble_bundle(pipeline_doc, document_path, root)
    findings = findings + validate_pipeline_bundle(bundle)
    # The bundle validator also enforces runnability (status must be 'active').
    # This plugin authors draft bundles by design, so for a non-active pipeline the
    # "not runnable" verdict is expected, not an authoring error — surface it as a
    # warning (informational) while keeping every referential finding blocking.
    if pipeline_doc.get("status") != "active":
        for f in findings:
            if f.get("validator") == "bundle-pipeline" and f.get("path") == "/pipeline/status":
                f["severity"] = "warning"
                f["message"] += (" (informational: this plugin authors draft bundles; "
                                 "runnability applies once status is 'active')")
    return findings


def diagnostics_for(entity: str, document_path: Path, bundle_root: Path | None = None) -> dict:
    """Validate one document and return the Diagnostics envelope. Raises nothing
    for validation failures — those become findings; only a genuinely unreadable
    document short-circuits."""
    try:
        doc = _read_json(document_path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _diagnostics([_finding("document", "error", "", f"Cannot read document: {exc}")])

    if entity == "database_endpoint":
        findings = _endpoint_findings(doc, document_path)
    else:
        findings = _model_findings(entity, doc)
        if entity == "pipeline" and bundle_root is not None:
            findings = findings + _bundle_findings(doc, document_path, bundle_root)
    return _diagnostics(findings)


def _read_json(path: Path):
    return json.loads(Path(path).read_text())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entity", required=True, choices=ENTITIES,
                        help="Which published contract the document is authored against.")
    parser.add_argument("--document", required=True, help="Path to the JSON document to validate.")
    parser.add_argument("--bundle-root",
                        help="Project root for cross-document validation of a stitched pipeline "
                             "(walks connections/, connectors/, and the pipeline's streams/). "
                             "Only meaningful with --entity pipeline.")
    args = parser.parse_args(argv)

    try:
        ensure_deps_or_reexec(__file__)
    except RuntimeError as exc:
        print(json.dumps(_diagnostics([_finding("contract-model", "error", "", str(exc))]), indent=2))
        return 1

    bundle_root = Path(args.bundle_root) if args.bundle_root else None
    diagnostics = diagnostics_for(args.entity, Path(args.document), bundle_root)
    print(json.dumps(diagnostics, indent=2))
    return 0 if diagnostics["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
