"""Every bundled reference example must validate against the pinned contract.

The `examples/*.example.json` files are what a creator agent copies its shape
from, so a drifted example teaches the agent to author an invalid document. This
suite is the guard: it validates each example against the entity its directory
implies, using the same adapter the `pipeline-schema-validator` agent runs.

Skips cleanly when the published packages are absent, like the other suites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "scripts"))
import validate as V  # noqa: E402

pytest.importorskip("analitiq.validator",
                    reason="requires: pip install -r requirements-dev.txt")

# Which entity each spec skill's examples are authored as.
SKILL_ENTITY = {
    "pipeline-spec": "pipeline",
    "stream-spec": "stream",
    "connection-spec": "connection",
    "endpoint-spec": "database_endpoint",
}


def _examples():
    for skill, entity in sorted(SKILL_ENTITY.items()):
        for path in sorted((ROOT / "src" / "skills" / skill / "examples").glob("*.json")):
            yield pytest.param(entity, path, id=f"{skill}/{path.name}")


EXAMPLES = list(_examples())


def test_examples_are_discovered():
    """Guard the guard: a glob that silently matches nothing would pass vacuously."""
    assert len(EXAMPLES) >= 19, f"expected the bundled examples, found {len(EXAMPLES)}"


@pytest.mark.parametrize("entity,path", EXAMPLES)
def test_example_validates(entity, path):
    diagnostics = V.diagnostics_for(entity, path)
    assert diagnostics["passed"], (
        f"{path.relative_to(ROOT)} does not validate as {entity}: "
        + "; ".join(f"{f['path']}: {f['message']}" for f in diagnostics["findings"])
    )


@pytest.mark.parametrize("entity,path", EXAMPLES)
def test_example_declares_matching_schema_url(entity, path):
    """An example's `$schema` must name its own entity, so the file self-describes."""
    from analitiq.contracts.connection import CONNECTION_SCHEMA_URL
    from analitiq.contracts.endpoints import DATABASE_ENDPOINT_SCHEMA_URL
    from analitiq.contracts.pipelines.config import PIPELINE_SCHEMA_URL
    from analitiq.contracts.stream import STREAM_SCHEMA_URL

    expected = {
        "pipeline": PIPELINE_SCHEMA_URL,
        "stream": STREAM_SCHEMA_URL,
        "connection": CONNECTION_SCHEMA_URL,
        "database_endpoint": DATABASE_ENDPOINT_SCHEMA_URL,
    }[entity]
    assert json.loads(path.read_text()).get("$schema") == expected
