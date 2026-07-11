"""Tests for the validator adapter (scripts/validate.py).

The adapter holds no validation logic — it dispatches to the published
`analitiq-validator` / `analitiq-contract-models` packages. These tests therefore
require those packages installed (CI: `pip install -r requirements-dev.txt`); the
whole module skips cleanly when they are absent so a bare `pytest` never fails
confusingly. Canonical documents are defined inline and written to `tmp_path`, so
there are no committed fixtures to drift from the contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate as V  # noqa: E402

pytest.importorskip("analitiq.validator",
                    reason="requires: pip install -r requirements-dev.txt")
from analitiq.contracts.endpoint_identity import (  # noqa: E402
    build_database_object, derive_db_endpoint_id,
)

SRC = "22222222-2222-4222-8222-222222222222"
DST = "33333333-3333-4333-8333-333333333333"
PID = "11111111-1111-4111-8111-111111111111"
SID = "44444444-4444-4444-8444-444444444444"
EID = derive_db_endpoint_id(None, "public", "orders")
DBOBJ = build_database_object(None, "public", "orders")
H = "https://schemas.analitiq.ai"

CONN_WISE = {
    "$schema": f"{H}/connection/latest.json", "connection_id": SRC, "connector_id": "wise",
    "display_name": "Wise", "parameters": {"environment": "live"},
    "secret_refs": {"api_token": "env:ANALITIQ_WISE_API_TOKEN"},
}
CONN_PG = {
    "$schema": f"{H}/connection/latest.json", "connection_id": DST, "connector_id": "postgresql",
    "display_name": "Prod Postgres",
    "parameters": {"host": "db.example.com", "port": 5432, "database": "analytics", "ssl_mode": "verify-full"},
    "secret_refs": {"password": "env:ANALITIQ_POSTGRESQL_PASSWORD"},
}
PIPELINE = {
    "$schema": f"{H}/pipeline/latest.json", "pipeline_id": PID, "display_name": "Wise to Postgres",
    "connections": {"source": SRC, "destinations": [DST]}, "streams": [SID],
    "schedule": {"type": "manual", "timezone": "UTC"}, "status": "draft",
}
STREAM = {
    "$schema": f"{H}/stream/latest.json", "stream_id": SID, "pipeline_id": PID, "display_name": "orders",
    "source": {
        "endpoint_ref": {"scope": "connector", "connection_id": SRC, "endpoint_id": "transfers"},
        "replication": {"method": "incremental", "cursor_field": "updated_at"},
    },
    "destinations": [{
        "endpoint_ref": {"scope": "connection", "connection_id": DST, "endpoint_id": EID, "database_object": DBOBJ},
        "write": {"mode": "upsert", "conflict_keys": ["id"]},
    }],
    "status": "draft",
}
DB_ENDPOINT = {
    "$schema": f"{H}/database-endpoint/latest.json", "endpoint_id": EID, "display_name": "public.orders",
    "database_object": DBOBJ,
    "columns": [
        {"name": "id", "native_type": "bigint", "arrow_type": "Int64", "nullable": False, "ordinal_position": 1},
        {"name": "updated_at", "native_type": "timestamptz", "arrow_type": "Timestamp(MICROSECOND, UTC)",
         "nullable": False, "ordinal_position": 2},
    ],
    "primary_keys": ["id"],
}


def _write(root: Path, rel: str, doc: dict) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2))
    return p


@pytest.mark.parametrize("entity,doc", [
    ("connection", CONN_PG), ("connection", CONN_WISE),
    ("pipeline", PIPELINE), ("stream", STREAM), ("database_endpoint", DB_ENDPOINT),
])
def test_valid_single_document(tmp_path, entity, doc):
    diag = V.diagnostics_for(entity, _write(tmp_path, f"{entity}.json", doc))
    assert diag["passed"], diag["findings"]


@pytest.mark.parametrize("entity,doc,validator_id", [
    # legacy connection carrying a `values` envelope — no longer part of the contract
    ("connection",
     {"$schema": f"{H}/connection/latest.json", "connector_id": "postgresql", "values": {"host": "x"}},
     "contract-model"),
    # legacy stream: flat endpoint_ref (missing database_object) + list-of-lists conflict_keys
    ("stream",
     {"$schema": f"{H}/stream/latest.json", "pipeline_id": PID,
      "source": {"endpoint_ref": {"scope": "connection", "connection_id": SRC, "endpoint_id": "orders"}},
      "destinations": [{"endpoint_ref": {"scope": "connection", "connection_id": DST, "endpoint_id": "orders"},
                        "write": {"mode": "upsert", "conflict_keys": [["id"]]}}]},
     "contract-model"),
    # database endpoint whose id is not the derived handle
    ("database_endpoint",
     {"$schema": f"{H}/database-endpoint/latest.json", "endpoint_id": "public_orders",
      "database_object": DBOBJ, "columns": [{"name": "id", "native_type": "bigint", "arrow_type": "Int64"}]},
     "endpoint-id-locator"),
])
def test_invalid_single_document(tmp_path, entity, doc, validator_id):
    diag = V.diagnostics_for(entity, _write(tmp_path, f"{entity}.json", doc))
    assert not diag["passed"]
    assert any(f["validator"] == validator_id for f in diag["findings"]), diag["findings"]


def _build_bundle(root: Path) -> Path:
    _write(root, "connectors/wise/definition/connector.json", {"connector_id": "wise", "kind": "api"})
    _write(root, "connectors/postgresql/definition/connector.json", {"connector_id": "postgresql", "kind": "database"})
    _write(root, "connections/wise/connection.json", CONN_WISE)
    _write(root, "connections/postgresql/connection.json", CONN_PG)
    _write(root, f"connections/postgresql/endpoints/{EID}.json", DB_ENDPOINT)
    _write(root, "pipelines/p/streams/orders.json", STREAM)
    return _write(root, "pipelines/p/pipeline.json", PIPELINE)


def test_valid_draft_bundle(tmp_path):
    doc = _build_bundle(tmp_path)
    diag = V.diagnostics_for("pipeline", doc, bundle_root=tmp_path)
    assert diag["passed"], diag["findings"]
    # a draft pipeline is not runnable; that finding is surfaced but downgraded to a warning
    assert any(f["severity"] == "warning" and f["path"] == "/pipeline/status" for f in diag["findings"])


def test_bundle_referential_error(tmp_path):
    doc = _build_bundle(tmp_path)
    stream_path = tmp_path / "pipelines/p/streams/orders.json"
    stream = json.loads(stream_path.read_text())
    stream["source"]["endpoint_ref"]["connection_id"] = "99999999-9999-4999-8999-999999999999"
    stream_path.write_text(json.dumps(stream))
    diag = V.diagnostics_for("pipeline", doc, bundle_root=tmp_path)
    assert not diag["passed"]
    assert any(f["validator"] == "bundle-connection-ref" for f in diag["findings"]), diag["findings"]


def test_unreadable_document(tmp_path):
    diag = V.diagnostics_for("pipeline", tmp_path / "does_not_exist.json")
    assert not diag["passed"]
    assert diag["findings"][0]["validator"] == "document"


def test_cli_main_valid(tmp_path, capsys):
    p = _write(tmp_path, "pipeline.json", PIPELINE)
    rc = V.main(["--entity", "pipeline", "--document", str(p)])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["passed"] is True  # stdout carries exactly one JSON object


def test_cli_main_invalid_exit_code(tmp_path, capsys):
    bad = {"$schema": f"{H}/connection/latest.json", "connector_id": "x", "values": {}}
    p = _write(tmp_path, "connection.json", bad)
    rc = V.main(["--entity", "connection", "--document", str(p)])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_cli_usage_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        V.main(["--document", "x.json"])  # missing required --entity
    assert excinfo.value.code == 2


def test_endpoint_id_helper(capsys):
    import endpoint_id  # sibling of validate.py on sys.path
    rc = endpoint_id.main(["--schema", "public", "--name", "orders"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["endpoint_id"] == EID
    assert out["database_object"]["name"] == "orders"


def test_active_pipeline_not_runnable_stays_error(tmp_path):
    doc = _build_bundle(tmp_path)  # the bundled stream is draft
    pipe = json.loads(doc.read_text())
    pipe["status"] = "active"
    doc.write_text(json.dumps(pipe))
    diag = V.diagnostics_for("pipeline", doc, bundle_root=tmp_path)
    # an active pipeline with no runnable stream is a real error — the draft-status
    # downgrade must NOT fire here
    assert not diag["passed"]
    assert any(f["validator"] == "bundle-pipeline" and f["severity"] == "error"
               for f in diag["findings"]), diag["findings"]


def test_bundle_malformed_sibling(tmp_path):
    doc = _build_bundle(tmp_path)
    (tmp_path / "pipelines/p/streams/orders.json").write_text("{ not valid json")
    diag = V.diagnostics_for("pipeline", doc, bundle_root=tmp_path)
    assert not diag["passed"]
    assert any(f["validator"] == "document" for f in diag["findings"]), diag["findings"]


def test_bundle_non_dict_sibling(tmp_path):
    doc = _build_bundle(tmp_path)
    # valid JSON but not an object → the "is not a JSON object" branch (connection path)
    (tmp_path / "connections/postgresql/connection.json").write_text("[]")
    diag = V.diagnostics_for("pipeline", doc, bundle_root=tmp_path)
    assert not diag["passed"]
    assert any(f["validator"] == "document" and "not a JSON object" in f["message"]
               for f in diag["findings"]), diag["findings"]
