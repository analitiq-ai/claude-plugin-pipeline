# Filter operator vocabularies

Filters declared in `source.filters[]` draw from a per-endpoint-kind operator
vocabulary. The endpoint contract declares which operators each field or
parameter accepts, enforced server-side at save time (the stream schema leaves
`operator` an open string, so the local validator does not check it). Stick to
the vocabularies below.

## Database (`scope: connection`)

Allowed `operator` values:

| Category | operators |
|---|---|
| Comparison | `eq`, `neq`, `gt`, `gte`, `lt`, `lte` |
| Collection | `in`, `not_in` |
| Null check (unary) | `is_null`, `is_not_null` — must omit `value` |
| Pattern | `like`, `ilike` |

`like` / `ilike` accept SQL wildcard syntax in `value` (`%`, `_`).
The engine routes these to the dialect's pattern operator.

## API (`scope: connector`)

Allowed `operator` values:

| Category | operators |
|---|---|
| Comparison | `eq`, `neq`, `gt`, `gte`, `lt`, `lte` |
| Collection | `in`, `not_in` |
| String | `contains`, `starts_with`, `ends_with` |

API endpoints have **no** unary operators. The endpoint document
declares which subset of the above each parameter accepts via
`operations.read.params.<name>.allowed_operators`. The plugin can only
emit operators in the union; the registry validates against the per-
parameter subset at save time.

API filters may **not** target params with `controlled_by:
"pagination"` or `controlled_by: "replication"` — those are owned by
the runtime, not the stream. The runtime-side validator rejects them.

## Common to both

- Unary operators (`is_null`, `is_not_null`) omit `value`.
- All other operators include `value` matching the column's data type
  (or for `in` / `not_in`, an array of such values).
- `field` references a column (database) or parameter key (API).
  Field-existence is enforced server-side; the local validator does
  not resolve filter fields against endpoint files.
