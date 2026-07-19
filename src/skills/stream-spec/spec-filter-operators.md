# Filter operator vocabularies

Filters declared in `source.filters[]` draw from a closed, per-scope operator
vocabulary. The contract enforces it: `operator` is a closed Literal
(`analitiq.contracts.stream.FilterOperator`), and the operator must belong to the
**source scope's** vocabulary — a database operator on an API source, or the
reverse, fails local validation with `[ADV-STRM-012]`.

<!-- BEGIN GENERATED: filter-operators -->
| Availability | Operators |
|---|---|
| Both scopes | `eq`, `gt`, `gte`, `in`, `lt`, `lte`, `neq`, `not_in` |
| `scope: "connection"` (database) only | `ilike`, `is_not_null`, `is_null`, `like` |
| `scope: "connector"` (API) only | `contains`, `ends_with`, `starts_with` |

`is_null`, `is_not_null` are unary — they must omit `value`; every other operator requires it.
<!-- END GENERATED: filter-operators -->

## Authoring notes

- `like` / `ilike` accept SQL wildcard syntax in `value` (`%`, `_`). The engine
  routes these to the dialect's pattern operator.
- All non-unary operators include `value` matching the column's data type — or,
  for `in` / `not_in`, an array of such values.
- `field` references a column (database) or a parameter key (API).

## What the local validator still cannot check

Field-existence is **not** resolved locally — the validator does not read filter
fields against endpoint files, so a typo in `field` passes here and fails
server-side at save time. Read the field name back to the user rather than
guessing it.

For an API source, the endpoint document narrows the vocabulary further:
`operations.read.params.<name>.allowed_operators` declares the subset each
parameter accepts. The plugin can only tell that an operator is in the API set;
the registry validates it against the per-parameter subset on save.

API filters may **not** target params with `controlled_by: "pagination"` or
`controlled_by: "replication"` — those are owned by the runtime, not the stream,
and the runtime-side validator rejects them.
