# The connection envelope

A connection document has **four author-time maps**, each keyed by a
connection-contract input or post-auth-output name. There is no single `values`
object — the plugin routes each key into the right map itself, driven entirely by
the connector's contract:

| Map | Holds | Sourced from a contract entry whose… |
|---|---|---|
| `parameters` | non-secret submitted values | input `storage: "connection.parameters"` |
| `secret_refs` | pointers to secret values (never the value) | input/output `storage: "secrets"` |
| `selections` | durable post-auth user choices | output `storage: "connection.selections"` |
| `discovered` | provider-returned non-secret values | output `storage: "connection.discovered"` — **server-managed, never authored** |

`connector_id` is the only schema-required field. Every map is optional; omit any
that would be empty.

## Routing rule (the whole thing)

Read the downloaded connector's `connection_contract`. For each
`inputs.<key>` and `post_auth_outputs.<key>`, route by the **last segment of its
`storage`** literal — this single rule covers every connector and auth type, so
nothing here changes when a new connector ships:

- `connection.parameters` → `parameters.<key>` = the user's value.
- `secrets` → `secret_refs.<key>` = a secret **pointer** (see below); the value
  goes in `.secrets/`, never the document.
- `connection.selections` → `selections.<key>` **only if** the user supplies it
  up front; usually omit (a post-auth selection isn't known at authoring time).
- `connection.discovered` → **never author.** The auto-discovery pipeline writes
  this bucket; the connections API rejects a client-supplied value.

## Type fidelity

Each contract input declares a JSON `type`. The authored value must use that type
verbatim — `port: 5432` (integer), not `"5432"`. The plugin does not coerce;
read the type from the connector or ask the user. Inputs with `enum: [...]`
accept only a listed value (e.g. `ssl_mode`). Optional inputs (`required: false`)
may be omitted; do not copy a connector's `default` into the document unless the
user is overriding it.

## Secrets — reference, never embed

For every input/output the contract marks `storage: "secrets"`, write a
**pointer** into `secret_refs.<key>`, and record the real value in a gitignored
`.secrets/credentials.json` the user provisions. The plugin never holds, logs, or
writes a secret value into the document.

Author an **`env:` pointer** by default — portable and resolved from the runtime
environment:

```jsonc
{
  "connector_id": "postgresql",
  "parameters": { "host": "db.example.com", "port": 5432, "database": "analytics", "ssl_mode": "verify-full" },
  "secret_refs": { "password": "env:ANALITIQ_POSTGRESQL_PASSWORD" }
}
```

Env-var name: `ANALITIQ_<connection-slug>_<key>`, upper-cased, every
non-alphanumeric replaced with `_` (matches the `env:` grammar
`[A-Za-z_][A-Za-z0-9_]*`). Emit the sibling template the user fills in:

```jsonc
// .secrets/credentials.json
{ "ANALITIQ_POSTGRESQL_PASSWORD": "<paste-password-here>" }
```

The user (or CI) exports these into the environment where the pipeline runs (or
loads them into their secret store) before submission; the plugin never reads
`.secrets/`.

Use `env:` unless the user asks for a specific store; substitute their pointer
verbatim if so. `sidecar:NAME` names an entry in the connection's local
credentials file.

<!-- BEGIN GENERATED: secret-ref-grammar -->
Every `secret_refs` value must carry an explicit scheme — a bare token (a pasted raw secret) is rejected by the contract.

Accepted schemes (`analitiq.contracts.connection.SECRET_REF_VALUE_PATTERN`):

- `env:[A-Za-z_][A-Za-z0-9_]*`
- `file:[A-Za-z0-9_.][A-Za-z0-9_./\-]*`
- `s3://[A-Za-z0-9._\-]+/[A-Za-z0-9_./\-]+`
- `arn:aws:secretsmanager:[A-Za-z0-9\-]+:\d+:secret:[A-Za-z0-9/_\-+=.@]+`
- `arn:aws:ssm:[A-Za-z0-9\-]+:\d+:parameter/[A-Za-z0-9_./\-]+`
- `ssm:/[A-Za-z0-9_./\-]+`
- `sidecar:.+`
<!-- END GENERATED: secret-ref-grammar -->
