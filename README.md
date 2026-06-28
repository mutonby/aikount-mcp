# Aikount MCP server

Bring your Spanish accounting into any AI agent. This is a [Model Context
Protocol](https://modelcontextprotocol.io) server that exposes the
[Aikount](https://aikount.com) API as tools, so Claude, Cursor, ChatGPT,
Claude Code, OpenCode, Gemini CLI and any other MCP client can issue
invoices, capture expense PDFs, reconcile bank movements and prepare Spanish
tax models (Modelo 303) directly in your books.

Aikount is an agent-first alternative to Holded for autónomos and pymes. The
API is the product; this server is the native bridge into the agent
ecosystem.

## Tools

| Tool | What it does |
|------|--------------|
| `whoami` | Verify the token, return the active tenant |
| `list_contacts` / `create_contact` | Customers & suppliers |
| `list_tax_types` | Tax UUIDs (21% IVA, reducido, IGIC/IPSI, IRPF) for invoice lines |
| `list_products` | Catalog products/services |
| `list_invoices` / `get_invoice` | Read sales invoices |
| `create_invoice` / `issue_invoice` | Draft then issue (assigns the legal number) |
| `list_purchases` / `get_purchase` | Read expenses |
| `ingest_purchase_pdf` / `get_ingest_job` | OCR a PDF into a **deduplicated** purchase |
| `list_treasuries` | Bank / Stripe / PayPal accounts with balances |
| `list_bank_movements` | Bank movements, filterable |
| `reconciliation_board` / `reconcile_movement` | Match movements ↔ documents |
| `list_accounts` | Spanish PGC chart of accounts (code → UUID) |
| `ledger` | Movements for one PGC account (by UUID) |
| `trial_balance` | Balance de sumas y saldos across all accounts |
| `modelo_303_summary` / `modelo_303_csv` | Quarterly VAT (JSON overview or AEAT CSV) |
| `api_request` | Escape hatch for any other endpoint (see the OpenAPI spec) |

> **Why no `create_purchase`?** Duplicate purchase invoices corrupt expense
> totals, IVA soportado and bank reconciliation. Raw `POST /purchases` does
> not deduplicate, so this server adds expenses only through
> `ingest_purchase_pdf`, which deduplicates by invoice identity. For other
> cases, use `api_request` consciously.

## Setup

You need an **API key** (scope `*`, prefixed `agl_`). Mint one with the
**"Conectar agente"** button in the Aikount web app — it shows you the exact
`export` lines.

```bash
export AIKOUNT_TOKEN="agl_xxxxxxxxxxxxxxxxxxxxxxxx"
# optional, defaults to production:
# export AIKOUNT_API="https://api.aikount.com/api/v1"
```

### Run it

With [uv](https://docs.astral.sh/uv/) (no install):

```bash
uvx aikount-mcp
```

Or with pip/pipx:

```bash
pipx install aikount-mcp   # or: pip install aikount-mcp
aikount-mcp
```

### Claude Desktop / Claude Code

Add to your MCP config (`claude_desktop_config.json`, or `.mcp.json` for
Claude Code):

```json
{
  "mcpServers": {
    "aikount": {
      "command": "uvx",
      "args": ["aikount-mcp"],
      "env": { "AIKOUNT_TOKEN": "agl_xxxxxxxxxxxxxxxxxxxxxxxx" }
    }
  }
}
```

### Cursor

Settings → MCP → Add new server, same `command` / `args` / `env` as above.

## Conventions (so the agent gets it right)

- **Money** is in major units (euros as decimals): `unit_price: 1200.00`,
  not cents. EUR unless `currency` says otherwise.
- **Dates** are ISO-8601 `YYYY-MM-DD`. **IDs** are UUIDs.
- Invoice/purchase lines reference taxes by `tax_type_id` (a UUID from
  `list_tax_types`), not a string code. Omit it to inherit the
  contact/product default.
- Errors come back as `{"error": true, "status_code": ..., "detail": ...,
  "hint": ...}` so the model can self-correct (re-auth on 401, fix the body
  on 422).
- The token has scope `*` — treat it like a password. Tenant isolation is
  automatic.

The [OpenAPI spec](https://api.aikount.com/openapi.json) is the source of
truth for everything this server doesn't wrap; reach it via `api_request`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # 23 unit tests, no network (httpx MockTransport)
```

The tests pin each tool to the **real** API path verified against the live
OpenAPI spec, so the routes can't silently regress.

`server.json` is the [official MCP registry](https://registry.modelcontextprotocol.io)
manifest for this package.

## License

MIT
