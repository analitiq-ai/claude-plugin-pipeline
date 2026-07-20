"""Gate the prose *outside* generated blocks (issue #24).

`test_generated_blocks_in_sync` verifies the contents of every marked region.
Nothing verified that a fact was inside a region at all — delete a marker pair,
hand-type a wrong vocabulary in its place, and the suite stayed green.

This closes that. For every closed vocabulary the contract owns:

  * it must be emitted by at least one generated block, so an authoritative copy
    exists somewhere an agent will read;
  * any doc that restates the *whole* vocabulary outside a block must be listed
    in ALLOWED_RESTATEMENTS with a reason.

The allow-list is the point. Naming members is often legitimate — a doc that
explains what each `schedule.type` means has to say `manual`, `interval` and
`cron`. What must not happen silently is a *new* hand-typed copy of a vocabulary
appearing with nobody having decided it should be hand-typed. A new restatement
fails here until someone either wires a block or writes down why not.

Detection is deliberately narrow: members must appear in backticks, and all of
them within one paragraph. A partial mention ("author `upsert` when the user
wants merge semantics") is guidance, not a restatement, and does not trip it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "scripts"))
import gen_contract_docs as G  # noqa: E402

pytest.importorskip("analitiq.validator",
                    reason="requires: pip install -r requirements-dev.txt")

# (doc path relative to src/, vocabulary key) -> why a hand-typed copy is correct here.
# Every entry is a deliberate decision, not a backlog.
ALLOWED_RESTATEMENTS = {
    ("skills/pipeline-builder/references/enum-mappers.md", "schedule.type"):
        "the phrasing->member mapping tables must name each target member; the "
        "authoritative list is the enum-vocabulary block at the top of the file",
    ("skills/pipeline-builder/references/enum-mappers.md", "replication.method"):
        "same: the mapper table's right-hand column IS the member",
    ("skills/pipeline-builder/references/enum-mappers.md", "write.mode"):
        "same: the mapper table's right-hand column IS the member",
    ("skills/pipeline-spec/spec-schedule.md", "schedule.type"):
        "one `## type: <member>` section per member — the document's structure is "
        "the enumeration, and each section explains that member's fields",
    ("skills/pipeline-spec/spec-schedule.md", "status"):
        "the status->scheduling-effect table; the rows explain behaviour per "
        "member, which the contract does not express",
    ("skills/pipeline-spec/spec-streams-and-status.md", "status"):
        "the status->runnability table; same reason",
    ("skills/stream-spec/spec-validation-rules.md", "validation_rule.type"):
        "per-member semantics (which types take a `value`), sitting beside the "
        "generated fields-validation-rule block",
    ("agents/stream-creator.md", "write.mode"):
        "states the conflict_keys rule (ADV-STRM-011), which distinguishes the "
        "two modes and so must name both",
}

# Vocabularies whose members are ordinary domain nouns, so "all members present"
# carries no signal. `endpoint_ref.scope` is {connector, connection}: both words
# appear in backticks throughout these docs for unrelated reasons, and any doc
# that contrasts the two ref shapes trips the detector. Allow-listing file by file
# would grow without bound and teach people to append rather than think.
# Still covered by test_every_vocabulary_is_emitted_by_some_block.
EXCLUDED_FROM_PROSE_GATE = {"endpoint_ref.scope"}

_TICKED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


def _paragraphs(text: str):
    """Yield (start_line, text) for each run of non-blank lines.

    A paragraph keeps a markdown table or bullet list together, which is the unit
    a restated vocabulary actually occupies.
    """
    buffer, start = [], 0
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not buffer:
                start = lineno
            buffer.append(line)
        elif buffer:
            yield start, "\n".join(buffer)
            buffer = []
    if buffer:
        yield start, "\n".join(buffer)


def _restatements():
    """Every (doc, vocab, line) where a full vocabulary appears outside a block."""
    vocabularies = {
        key: set(vocab["members"])
        for key, vocab in G.published_vocabularies().items()
        # A single-member "vocabulary" would match almost any mention.
        if len(vocab["members"]) > 1 and key not in EXCLUDED_FROM_PROSE_GATE
    }
    found = []
    for path in sorted(G.DOCS_ROOT.rglob("*.md")):
        outside_blocks = G._BLOCK_RE.sub("", path.read_text())
        rel = path.relative_to(G.DOCS_ROOT).as_posix()
        for start, paragraph in _paragraphs(outside_blocks):
            ticked = set(_TICKED.findall(paragraph))
            for key, members in vocabularies.items():
                if members <= ticked:
                    found.append((rel, key, start))
    return found


def test_every_vocabulary_is_emitted_by_some_block():
    """An authoritative generated copy of each vocabulary must exist in the docs."""
    # Per block, not concatenated across all of them: a union would let a
    # vocabulary's members be scattered over unrelated blocks and still "pass"
    # while no single block actually presents the vocabulary to a reader.
    bodies = [
        match.group("body")
        for path in G.generated_docs()
        for match in G._BLOCK_RE.finditer(path.read_text())
    ]
    assert any(b.strip() for b in bodies), "no generated block content — vacuous pass"
    ticked_per_block = [set(_TICKED.findall(b)) for b in bodies]
    missing = sorted(
        key for key, vocab in G.published_vocabularies().items()
        if not any(set(vocab["members"]) <= ticked for ticked in ticked_per_block)
    )
    assert not missing, (
        f"vocabularies no single generated block presents in full: {missing}. "
        "Wire a block that emits them, or an agent has only hand-typed copies to read.")


def test_no_undeclared_vocabulary_restatement():
    """A hand-typed copy of a whole vocabulary must be a recorded decision."""
    undeclared = sorted(
        {(doc, key) for doc, key, _ in _restatements()} - set(ALLOWED_RESTATEMENTS)
    )
    assert not undeclared, (
        "these docs restate a full closed vocabulary outside any generated block:\n"
        + "\n".join(f"  {doc}  [{key}]" for doc, key in undeclared)
        + "\n\nEither wire a generated block that emits it (preferred — then the "
          "copy cannot drift), or add an entry to ALLOWED_RESTATEMENTS in this "
          "file saying why a hand-typed copy is correct there."
    )


def test_exclusion_list_names_real_vocabularies():
    """A stale exclusion key silently gates nothing — the dead-constant failure.

    If a vocabulary is renamed or dropped upstream, its exclusion must not linger
    as an entry that quietly exempts a key nobody publishes any more.
    """
    unknown = sorted(EXCLUDED_FROM_PROSE_GATE - set(G.published_vocabularies()))
    assert not unknown, (
        f"EXCLUDED_FROM_PROSE_GATE names vocabularies the contract does not "
        f"publish: {unknown}. Remove them — they exempt nothing.")


def test_allow_list_has_no_stale_entries():
    """An allow-list that outlives its restatement quietly licenses a future one."""
    actual = {(doc, key) for doc, key, _ in _restatements()}
    stale = sorted(set(ALLOWED_RESTATEMENTS) - actual)
    assert not stale, (
        f"ALLOWED_RESTATEMENTS entries no longer match any restatement: {stale}. "
        "Remove them — the exemption they grant is now invisible and unearned.")
