#!/usr/bin/env python3
"""Render contract-owned facts from the published package into the prose docs.

The agent-facing prose under ``src/`` is the only prose Analitiq still keeps —
the schema contract itself is defined by the published ``analitiq-validator`` +
``analitiq-contract-models`` packages. Anything an agent needs that those
packages already state (enum members, regexes, required-field lists, bounds,
defaults, cross-field rule text) is therefore **generated** into the prose from
the installed package rather than retyped by hand, so a doc cannot drift from
the contract it documents.

Each generated region is delimited in the markdown by a marker pair::

    <!-- BEGIN GENERATED: <block-id> -->
    …emitted content…
    <!-- END GENERATED: <block-id> -->

Everything outside the markers is hand-written judgment (when to use a rule, how
to ask the user, what the plugin refuses to do) — this script never touches it.

Usage::

    python3 src/scripts/gen_contract_docs.py            # rewrite blocks in place
    python3 src/scripts/gen_contract_docs.py --check    # exit 1 if any block is stale

``--check`` is what CI runs: it regenerates into memory and diffs, so a pin bump
that changes the contract fails the build until the docs are regenerated.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from _analitiq import ensure_deps_or_reexec

# Repository-root-relative docs the generator is allowed to rewrite. A block id
# may appear in more than one file; every occurrence is rendered identically.
DOCS_ROOT = Path(__file__).resolve().parent.parent

_BLOCK_RE = re.compile(
    r"(?P<begin><!-- BEGIN GENERATED: (?P<id>[a-z0-9][a-z0-9-]*) -->\n)"
    r"(?P<body>.*?)"
    r"(?P<end><!-- END GENERATED: (?P=id) -->)",
    re.DOTALL,
)


class UnknownBlock(KeyError):
    """A doc references a block id no renderer produces — fail loud, never skip."""


# ---------------------------------------------------------------------------
# Renderers. Each takes no arguments and returns the markdown body for its
# block, WITHOUT the surrounding markers and ending in exactly one newline.
# ---------------------------------------------------------------------------

def _md_escape(text: str) -> str:
    """Escape a value for a markdown table cell.

    Only `|` and newlines need handling: every value emitted here lands inside a
    code span, where a backslash is literal — escaping it would corrupt the very
    regexes this generator exists to reproduce faithfully.
    """
    return text.replace("|", "\\|").replace("\n", " ")


def _code(value: object) -> str:
    return f"`{_md_escape(str(value))}`"


def render_schema_urls() -> str:
    from analitiq.contracts.connection import CONNECTION_SCHEMA_URL
    from analitiq.contracts.pipelines.config import PIPELINE_SCHEMA_URL
    from analitiq.contracts.stream import STREAM_SCHEMA_URL

    rows = [
        ("Pipeline", "pipeline.json", PIPELINE_SCHEMA_URL),
        ("Stream", "streams/<stream-slug>.json", STREAM_SCHEMA_URL),
        ("Connection", "connection.json", CONNECTION_SCHEMA_URL),
    ]
    out = ["| Entity | Authored file | `$schema` value |", "|---|---|---|"]
    out += [f"| {e} | {_code(f)} | {_code(u)} |" for e, f, u in rows]
    return "\n".join(out) + "\n"


def render_shared_vocabulary() -> str:
    from analitiq.contracts.shared import common
    from analitiq.contracts.shared import types

    rows = [
        ("Slug (ids + directory names)", "analitiq.contracts.shared.common.SLUG_PATTERN", common.SLUG_PATTERN),
        ("UUID (`*_id` identity fields)", "analitiq.contracts.shared.types.UUID_PATTERN", types.UUID_PATTERN),
        ("Cron expression", "analitiq.contracts.shared.common.CRON_PATTERN", common.CRON_PATTERN),
        ("No edge whitespace (`display_name`, tags)", "analitiq.contracts.shared.common.NO_EDGE_WHITESPACE_PATTERN",
         common.NO_EDGE_WHITESPACE_PATTERN),
    ]
    out = ["| Concern | Published constant | Pattern |", "|---|---|---|"]
    out += [f"| {c} | {_code(n)} | {_code(v)} |" for c, n, v in rows]
    out.append("")
    bounds = [
        ("`display_name` length", f"{common.DISPLAY_NAME_MIN}..{common.DISPLAY_NAME_MAX}"),
        ("`description` max length", str(common.DESCRIPTION_MAX)),
        ("`tags` max count", str(common.TAGS_MAX)),
        ("tag length", f"{common.TAG_MIN_LEN}..{common.TAG_MAX_LEN}"),
    ]
    out += ["| Bound | Value |", "|---|---|"]
    out += [f"| {label} | {_code(value)} |" for label, value in bounds]
    return "\n".join(out) + "\n"


def render_secret_ref_grammar() -> str:
    from analitiq.contracts.connection import SECRET_REF_VALUE_PATTERN

    schemes = SECRET_REF_VALUE_PATTERN.removeprefix("^(?:").removesuffix(")$").split("|")
    out = [
        "Every `secret_refs` value must carry an explicit scheme — a bare token "
        "(a pasted raw secret) is rejected by the contract.",
        "",
        "Accepted schemes (`analitiq.contracts.connection.SECRET_REF_VALUE_PATTERN`):",
        "",
    ]
    out += [f"- `{s}`" for s in schemes]
    return "\n".join(out) + "\n"


_UNARY_OPERATORS = ("is_null", "is_not_null")

_PROBE_UUID = "11111111-1111-4111-8111-111111111111"


def _accepted_operators_by_scope() -> dict[str, list[str]]:
    """Which filter operators the contract accepts for each endpoint-ref scope.

    The per-scope vocabularies exist in the package only as private constants, so
    this probes the public model instead: validate a minimal stream carrying one
    filter and keep the operators that survive. That cannot drift from the
    contract the way a transcribed list can, and it survives a rename of the
    package's internals.
    """
    from typing import get_args

    from pydantic import ValidationError

    from analitiq.contracts.stream import FilterOperator, StreamInput

    def endpoint_ref(scope: str) -> dict:
        if scope == "connection":
            return {"scope": "connection", "connection_id": _PROBE_UUID,
                    "database_object": {"name": "t", "schema": "public"}}
        return {"scope": "connector", "connection_id": _PROBE_UUID, "endpoint_id": "e"}

    def stream_doc(scope: str, filter_: dict | None) -> dict:
        source: dict = {"endpoint_ref": endpoint_ref(scope)}
        if filter_ is not None:
            source["filters"] = [filter_]
        return {"pipeline_id": _PROBE_UUID, "source": source,
                "destinations": [{"endpoint_ref": endpoint_ref("connection"),
                                  "write": {"mode": "insert"}}]}

    accepted: dict[str, list[str]] = {}
    for scope in ("connection", "connector"):
        # Guard the probe itself: if the baseline (no filters) stops validating,
        # every operator would silently look rejected and the block would render
        # empty. Fail loud instead.
        try:
            StreamInput.model_validate(stream_doc(scope, None))
        except ValidationError as exc:
            raise RuntimeError(
                f"filter-operator probe baseline no longer validates for scope "
                f"{scope!r}; the minimal stream shape in this generator needs "
                f"updating for the pinned contract: {exc}") from exc
        operators = []
        for operator in get_args(FilterOperator):
            probe = {"field": "x", "operator": operator}
            if operator not in _UNARY_OPERATORS:
                probe["value"] = "y"
            try:
                StreamInput.model_validate(stream_doc(scope, probe))
            except ValidationError:
                continue
            operators.append(operator)
        accepted[scope] = operators
    return accepted


def render_filter_operators() -> str:
    accepted = _accepted_operators_by_scope()
    connection, connector = set(accepted["connection"]), set(accepted["connector"])
    groups = [
        ("Both scopes", connection & connector),
        ('`scope: "connection"` (database) only', connection - connector),
        ('`scope: "connector"` (API) only', connector - connection),
    ]
    out = ["| Availability | Operators |", "|---|---|"]
    for label, members in groups:
        out.append(f"| {label} | {', '.join(f'`{m}`' for m in sorted(members))} |")
    out += [
        "",
        f"`{'`, `'.join(_UNARY_OPERATORS)}` are unary — they must omit `value`; "
        "every other operator requires it.",
    ]
    return "\n".join(out) + "\n"


def _advisory_block(prefixes: tuple[str, ...]) -> str:
    from analitiq.contracts.shared.advisory import all_rules

    rules = sorted(
        (r for r in all_rules() if r.id.startswith(prefixes)),
        key=lambda r: r.id,
    )
    if not rules:
        raise RuntimeError(f"no advisory rules matched {prefixes!r}")
    out = ["| Rule | Constraint |", "|---|---|"]
    out += [f"| {_code(r.id)} | {_md_escape(r.prose)} |" for r in rules]
    return "\n".join(out) + "\n"


def render_advisory_pipeline() -> str:
    return _advisory_block(("ADV-PIPE-", "ADV-RETRY-"))


def render_advisory_stream() -> str:
    return _advisory_block(("ADV-STRM-",))


def render_validator_ids() -> str:
    from analitiq.validator import VALIDATOR_IDS

    out = [
        "Validator ids the published package can emit:",
        "",
        ", ".join(f"`{v}`" for v in sorted(VALIDATOR_IDS)),
    ]
    return "\n".join(out) + "\n"


RENDERERS = {
    "schema-urls": render_schema_urls,
    "shared-vocabulary": render_shared_vocabulary,
    "secret-ref-grammar": render_secret_ref_grammar,
    "filter-operators": render_filter_operators,
    "advisory-pipeline": render_advisory_pipeline,
    "advisory-stream": render_advisory_stream,
    "validator-ids": render_validator_ids,
}


# ---------------------------------------------------------------------------
# Block substitution
# ---------------------------------------------------------------------------

def render_text(text: str, source: str) -> str:
    """Return `text` with every generated block re-rendered from the package."""

    def _sub(match: re.Match) -> str:
        block_id = match.group("id")
        try:
            renderer = RENDERERS[block_id]
        except KeyError:
            raise UnknownBlock(
                f"{source}: no renderer for generated block {block_id!r}; "
                f"known blocks: {', '.join(sorted(RENDERERS))}"
            ) from None
        return match.group("begin") + renderer() + match.group("end")

    return _BLOCK_RE.sub(_sub, text)


def generated_docs() -> list[Path]:
    """Every markdown file under src/ that carries at least one generated block."""
    return sorted(
        p for p in DOCS_ROOT.rglob("*.md")
        if "<!-- BEGIN GENERATED:" in p.read_text()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="Do not write; exit 1 if any generated block is stale.")
    args = parser.parse_args(argv)

    ensure_deps_or_reexec(__file__)

    docs = generated_docs()
    if not docs:
        print("no documents carry a generated block", file=sys.stderr)
        return 1

    stale: list[str] = []
    for path in docs:
        current = path.read_text()
        rendered = render_text(current, str(path))
        if current == rendered:
            continue
        rel = path.relative_to(DOCS_ROOT.parent)
        if args.check:
            stale.append(rel.as_posix())
            sys.stdout.writelines(difflib.unified_diff(
                current.splitlines(keepends=True), rendered.splitlines(keepends=True),
                fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        else:
            path.write_text(rendered)
            print(f"regenerated {rel}")

    if args.check and stale:
        print(f"\n{len(stale)} document(s) out of sync with the published contract: "
              f"{', '.join(stale)}\nRun: python3 src/scripts/gen_contract_docs.py",
              file=sys.stderr)
        return 1
    if args.check:
        print(f"{len(docs)} document(s) in sync with the published contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
