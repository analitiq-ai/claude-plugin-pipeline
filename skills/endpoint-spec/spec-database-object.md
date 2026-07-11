# `database_object` block

```jsonc
{
  "database_object": {
    "catalog": "analytics-prod",     // optional; e.g. database name, BigQuery project ID
    "schema": "warehouse",           // optional; e.g. PostgreSQL schema, BigQuery dataset
    "name": "orders",                // required
    "object_type": "table"           // optional; descriptive string
  }
}
```

## Identifier preservation

**All identifier strings are stored verbatim from introspection** — no
case-folding, quoting, or normalization. PostgreSQL is case-sensitive
when quoted, BigQuery names are case-sensitive in the catalog API,
and MongoDB collection names are case-sensitive throughout. Whatever
the source database reports, that's what goes here.

The hashing layer (`schema_hash`, server-managed) relies on this
verbatim preservation. Normalizing breaks the hash and triggers false
drift.

## Derived `endpoint_id`

`database_object` and the endpoint's `endpoint_id` are two views of one identity:
`endpoint_id` is derived from `(catalog, schema, name)` as
`slug(schema)__slug(name)[__slug(catalog)]__hash8`, the hash taken over the
**verbatim** identifiers. Compute both together with `scripts/endpoint_id.py`
(see `private-endpoint-creator`) so they always agree and match what the
validator recomputes.

## `name`

Required. Provider-native object identifier. `minLength: 1`. No quoting
or escaping — the value is the raw identifier as it appears in the
catalog.

## `catalog`

Optional. The outermost containment level when the dialect has one:

| Dialect | what goes in `catalog` |
|---|---|
| BigQuery | project ID (`analytics-prod`) |
| Snowflake | database name (`PROD_DB`) |
| SQL Server | database name (`master`) |
| Trino / Presto | catalog name (`hive`) |
| MongoDB | database name (`analytics`) |
| PostgreSQL | database name (often omitted; the connection already identifies it) |

## `schema`

Optional. The intermediate namespace:

| Dialect | what goes in `schema` |
|---|---|
| PostgreSQL | schema (`public`) |
| Snowflake / SQL Server | schema (`DBO`) |
| BigQuery | dataset (`warehouse`) |
| MongoDB | (omitted; collections live directly in the database) |

## `object_type`

Optional. Descriptive — **not** a closed enum. Common values:
`table`, `view`, `materialized_view`, `collection`, `external_table`,
`stream`. The catalog stores this verbatim; downstream tools may inspect
it for behavioral hints (e.g., "don't write to a view").

## Uniqueness

The tuple `(catalog, schema, name)` must be unique within the owner (the
connection that owns this endpoint). Column-name and primary-key issues are
caught by the contract model at the document level; cross-file uniqueness of
`database_object` tuples is enforced server-side at catalog-merge time.
