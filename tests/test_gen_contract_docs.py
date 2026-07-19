"""Tests for the contract-doc generator (src/scripts/gen_contract_docs.py).

The prose under `src/` is the only prose Analitiq still keeps, so the facts it
states about the contract are generated from the pinned published package rather
than typed by hand. The load-bearing test here is `test_generated_blocks_in_sync`:
it is the drift gate. If a pin bump changes an enum, a regex, a bound, or an
advisory rule, that test fails until the docs are regenerated.

Like the adapter tests, this module skips cleanly when the published packages are
absent so a bare `pytest` never fails confusingly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "scripts"))
import gen_contract_docs as G  # noqa: E402

pytest.importorskip("analitiq.validator",
                    reason="requires: pip install -r requirements-dev.txt")


def test_generated_blocks_in_sync():
    """Every generated block in every doc matches what the pinned package emits.

    This is the drift gate. On failure, run:
        python3 src/scripts/gen_contract_docs.py
    """
    stale = [
        p.relative_to(ROOT).as_posix()
        for p in G.generated_docs()
        if p.read_text() != G.render_text(p.read_text(), str(p))
    ]
    assert not stale, (
        "generated blocks are out of sync with the published contract in: "
        f"{', '.join(stale)}. Run: python3 src/scripts/gen_contract_docs.py"
    )


def test_every_doc_block_has_a_renderer():
    """A block id with no renderer must fail loud, not be silently left alone."""
    referenced = {
        m.group("id")
        for p in G.generated_docs()
        for m in G._BLOCK_RE.finditer(p.read_text())
    }
    assert referenced, "expected at least one generated block across the docs"
    assert referenced <= set(G.RENDERERS), (
        f"docs reference block ids with no renderer: "
        f"{sorted(referenced - set(G.RENDERERS))}"
    )


def test_unknown_block_id_raises():
    text = ("<!-- BEGIN GENERATED: no-such-block -->\n"
            "stale\n"
            "<!-- END GENERATED: no-such-block -->")
    with pytest.raises(G.UnknownBlock):
        G.render_text(text, "<test>")


def test_render_is_idempotent():
    """Rendering twice equals rendering once — no block grows or accumulates."""
    for path in G.generated_docs():
        once = G.render_text(path.read_text(), str(path))
        assert G.render_text(once, str(path)) == once, f"{path} render is not idempotent"


def test_content_outside_markers_is_untouched():
    text = ("Hand-written intro.\n\n"
            "<!-- BEGIN GENERATED: validator-ids -->\n"
            "obsolete body\n"
            "<!-- END GENERATED: validator-ids -->\n\n"
            "Hand-written outro.\n")
    rendered = G.render_text(text, "<test>")
    assert rendered.startswith("Hand-written intro.\n\n")
    assert rendered.endswith("\nHand-written outro.\n")
    assert "obsolete body" not in rendered


@pytest.mark.parametrize("block_id", sorted(G.RENDERERS))
def test_renderer_emits_nonempty_block(block_id):
    """Each renderer produces content ending in exactly one newline.

    Guards the failure mode where a renamed package symbol makes a renderer
    silently emit nothing, quietly deleting a rule from the agent's instructions.
    """
    body = G.RENDERERS[block_id]()
    assert body.strip(), f"{block_id} rendered empty"
    assert body.endswith("\n") and not body.endswith("\n\n"), (
        f"{block_id} must end with exactly one newline")


def test_filter_operator_scopes_are_disjoint_and_complete():
    """The empirically probed operator vocabulary matches the published Literal."""
    from typing import get_args

    from analitiq.contracts.stream import FilterOperator

    accepted = G._accepted_operators_by_scope()
    union = set(accepted["connection"]) | set(accepted["connector"])
    assert union == set(get_args(FilterOperator)), (
        "probe did not reproduce the full published operator vocabulary")
    # Each scope must genuinely restrict — if the probe silently accepted
    # everything, the generated table would be wrong but still look plausible.
    assert set(accepted["connection"]) != set(accepted["connector"])
