# Installing Aikount MCP (guide for AI agents like Cline)

This file tells an AI agent exactly how to install and configure the Aikount
MCP server. Aikount is an agent-first Spanish accounting SaaS; this server lets
you issue invoices, capture expense PDFs, reconcile bank movements and prepare
the Modelo 303 over its REST API.

## 1. Prerequisites

- **uv** (provides `uvx`). If it isn't installed, install it first:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Alternatively, `pip install aikount-mcp` and use the `aikount-mcp` command.
- An **Aikount API key** (a token prefixed `agl_`, scope `*`). The user mints it
  from the Aikount web app with the **"Conectar agente"** button. If the user
  doesn't have one yet, ask them to create it there — do not invent a token.

## 2. Configuration

Add this to the MCP settings file (e.g. Cline's `cline_mcp_settings.json`,
Claude Desktop's `claude_desktop_config.json`, or `.cursor/mcp.json`). Replace
`agl_your_token` with the user's real key:

```json
{
  "mcpServers": {
    "aikount": {
      "command": "uvx",
      "args": ["aikount-mcp"],
      "env": {
        "AIKOUNT_TOKEN": "agl_your_token"
      }
    }
  }
}
```

Optional: set `AIKOUNT_API` to point at a staging/self-hosted backend
(defaults to `https://api.aikount.com/api/v1`).

## 3. Verify

After the client reloads the MCP servers, call the **`whoami`** tool. A
successful response returns the active tenant (id, name, VAT), confirming the
token works. A 401/403 means the token is missing or invalid — ask the user to
re-mint it with "Conectar agente".

## 4. First things to try

- `list_invoices` — recent sales invoices.
- `list_treasuries` — bank / Stripe / PayPal accounts with balances.
- `modelo_303_summary` — quarterly VAT (Modelo 303) overview.

## Notes

- Money is in decimal euros (e.g. `1200.00`), not cents.
- The token has full scope — treat it like a password; never echo it back.
- Listing tools needs no token, so the server starts fine for introspection;
  a valid token is only required when a tool actually reads/writes the books.
