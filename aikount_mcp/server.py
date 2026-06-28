"""Aikount MCP server.

Exposes the Aikount accounting API as Model Context Protocol tools so any
MCP client (Claude Desktop, Cursor, Claude Code, OpenCode, …) can read and
write the user's books. Every path below was verified against the live
OpenAPI spec at https://api.aikount.com/openapi.json — it deliberately does
*not* follow the human cheat-sheet skill, which is out of date on several
routes (e.g. treasuries live at /treasuries, not /banking/treasuries).

Auth: set AIKOUNT_TOKEN (an 'agl_...' API key, scope *) in the environment.
Optionally set AIKOUNT_API to point at a staging/self-hosted backend.
"""

from __future__ import annotations

import functools
import mimetypes
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import AikountClient, AikountError, client_from_env

mcp = FastMCP("aikount")

# Lazily-built singleton so importing the module (tests, --help) never needs
# a token. The client is created on the first tool call.
_client: AikountClient | None = None


def get_client() -> AikountClient:
    global _client
    if _client is None:
        _client = client_from_env()
    return _client


def tool(fn):
    """Register an MCP tool that returns API errors as data instead of crashing.

    MCP clients render a tool that returns ``{"error": ...}`` far more usefully
    than one that raises — the model sees the status code and detail and can
    correct course (re-auth on 401, fix the body on 422, …).
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AikountError as exc:
            return {
                "error": True,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "hint": _hint_for(exc.status_code),
            }

    return mcp.tool()(wrapper)


def _hint_for(status: int) -> str | None:
    if status == 401:
        return "Token missing/revoked. Re-run 'Conectar agente' and re-export AIKOUNT_TOKEN."
    if status == 403:
        return "Token valid but lacks the required scope."
    if status == 404:
        return "Not found — check the id."
    if status == 422:
        return "Validation error — check field names/types against the detail."
    if status >= 500:
        return "Server error — transient, retry once."
    return None


# ===========================================================================
# Identity & master data
# ===========================================================================
@tool
def whoami() -> Any:
    """Verify the token and return the active tenant (id, name, VAT, currency…).

    Call this first. A 200 confirms the token works; a 401/403 means it is
    missing, revoked, or malformed.

    Note: with an 'agl_' API key this reads /tenants/me. The /auth/me endpoint
    is reserved for interactive session logins (onboarding/membership flow)
    and deliberately rejects API keys.
    """
    return get_client().get("/tenants/me")


@tool
def list_contacts(
    search: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List contacts (customers and suppliers).

    Args:
        search: free-text match on name / legal name / VAT.
        kind: 'customer' or 'supplier' to filter; omit for both.
        limit: page size (1-500, default 50).
        offset: pagination offset.
    """
    return get_client().get(
        "/contacts", search=search, kind=kind, limit=limit, offset=offset
    )


@tool
def create_contact(
    name: str,
    vat: str | None = None,
    email: str | None = None,
    country: str | None = None,
    is_customer: bool = True,
    is_supplier: bool = True,
    legal_name: str | None = None,
    notes: str | None = None,
) -> Any:
    """Create a contact. `country` is an ISO-3166 alpha-2 code (e.g. 'ES')."""
    body = {
        "name": name,
        "vat": vat,
        "email": email,
        "country": country,
        "is_customer": is_customer,
        "is_supplier": is_supplier,
        "legal_name": legal_name,
        "notes": notes,
    }
    return get_client().post("/contacts", json={k: v for k, v in body.items() if v is not None})


@tool
def list_tax_types() -> Any:
    """List the tenant's tax types (IVA/IGIC/IPSI/IRPF), each with its UUID.

    Invoice/purchase lines reference a tax by `tax_type_id` (a UUID from this
    list), not by a string code — call this to resolve which UUID is the 21%
    IVA, the 10% reducido, exento, etc.
    """
    return get_client().get("/taxes")


@tool
def list_products(search: str | None = None, limit: int = 50, offset: int = 0) -> Any:
    """List catalog products/services."""
    return get_client().get("/products", search=search, limit=limit, offset=offset)


# ===========================================================================
# Sales invoices
# ===========================================================================
@tool
def list_invoices(
    status: str | None = None,
    contact_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List sales invoices. Lifecycle: draft -> issued -> paid.

    Args:
        status: e.g. 'draft', 'issued', 'paid'.
        contact_id: filter to one customer (UUID).
        from_date / to_date: ISO 'YYYY-MM-DD' bounds on doc_date.
    """
    return get_client().get(
        "/invoices",
        status=status,
        contact_id=contact_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@tool
def get_invoice(doc_id: str) -> Any:
    """Fetch one sales invoice in full by UUID."""
    return get_client().get(f"/invoices/{doc_id}")


@tool
def create_invoice(
    contact_id: str,
    doc_date: str,
    lines: list[dict[str, Any]],
    due_date: str | None = None,
    currency: str = "EUR",
    notes: str | None = None,
    series_id: str | None = None,
) -> Any:
    """Create a DRAFT sales invoice (call issue_invoice to assign a number).

    Money is in MAJOR units (euros as decimals), e.g. unit_price 1200.00 —
    NOT cents. Each line is a dict:
        {
          "description": "Consultoría mayo",   # required
          "quantity": 1,                         # default 1
          "unit_price": 1200.00,                 # default 0, euros
          "tax_type_id": "<uuid>",               # from list_tax_types; omit
                                                  #   to inherit the contact/
                                                  #   product default
          "discount_pct": 0,                     # optional, 0-100
          "irpf_rate": 0                          # optional override, 0-100
        }

    Args:
        contact_id: customer UUID (see list_contacts / create_contact).
        doc_date: ISO 'YYYY-MM-DD'.
        series_id: optional numbering-series override (UUID).
    """
    body: dict[str, Any] = {
        "doc_type": "invoice",
        "contact_id": contact_id,
        "doc_date": doc_date,
        "currency": currency,
        "lines": lines,
    }
    if due_date is not None:
        body["due_date"] = due_date
    if notes is not None:
        body["notes"] = notes
    if series_id is not None:
        body["series_id"] = series_id
    return get_client().post("/invoices", json=body)


@tool
def issue_invoice(doc_id: str) -> Any:
    """Issue a draft invoice — assigns the next sequential legal number.

    Irreversible-ish: issued numbers must stay contiguous, so do not delete
    issued invoices to "renumber". Confirm with the user before issuing.
    """
    return get_client().post(f"/invoices/{doc_id}/issue")


# ===========================================================================
# Purchases (expenses)
# ===========================================================================
# NOTE: we deliberately do NOT expose a raw "create_purchase" tool. Manual
# POST /purchases does not deduplicate, and duplicate purchases corrupt
# expense totals, IVA soportado and bank reconciliation — the #1 thing the
# owner does not tolerate. Adding a purchase goes through the AI ingest path
# (ingest_purchase_pdf), which deduplicates by invoice identity.
@tool
def list_purchases(
    contact_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List purchase documents (supplier invoices / expenses)."""
    return get_client().get(
        "/purchases",
        contact_id=contact_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@tool
def get_purchase(doc_id: str) -> Any:
    """Fetch one purchase document in full by UUID."""
    return get_client().get(f"/purchases/{doc_id}")


@tool
def ingest_purchase_pdf(file_path: str, force: bool = False) -> Any:
    """Queue a purchase PDF/image for AI extraction (OCR -> deduped purchase).

    The AI reads the supplier, lines and taxes and creates the purchase doc,
    deduplicating by invoice identity (contact + supplier_invoice_number,
    fallback total + date) so the same invoice never lands twice. Runs async:
    this returns a job immediately — poll get_ingest_job(job_id) until its
    status is done, then read result for the created document.

    Args:
        file_path: local path to a PDF / JPG / PNG / WebP / HEIC.
        force: bypass dedup and ingest anyway (use only when you are sure it
               is a genuinely distinct invoice).
    """
    p = Path(file_path).expanduser()
    if not p.is_file():
        return {"error": True, "detail": f"File not found: {p}"}
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return get_client().post_file(
        "/ai/ingest-purchase",
        filename=p.name,
        content=p.read_bytes(),
        mime=mime,
        fields={"force": force},
    )


@tool
def get_ingest_job(job_id: str) -> Any:
    """Poll the status/result of an AI ingest job (see ingest_purchase_pdf)."""
    return get_client().get(f"/ai/ingest-jobs/{job_id}")


# ===========================================================================
# Banking & reconciliation
# ===========================================================================
@tool
def list_treasuries(limit: int = 50, offset: int = 0) -> Any:
    """List treasuries (bank / Stripe / PayPal accounts) with balances.

    Stripe/PayPal treasuries return a live balance pulled on read; bank-feed
    treasuries return the last synced snapshot.
    """
    return get_client().get("/treasuries", limit=limit, offset=offset)


@tool
def list_bank_movements(
    treasury_id: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List bank movements, optionally scoped to one treasury.

    Args:
        treasury_id: restrict to a single treasury (UUID).
        status: e.g. 'unreconciled' / 'reconciled'.
        from_date / to_date: ISO date bounds.
        search: free-text match on the movement description.
    """
    return get_client().get(
        "/bank-movements",
        treasury_id=treasury_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        search=search,
        limit=limit,
        offset=offset,
    )


@tool
def reconciliation_board() -> Any:
    """Get the reconciliation board: suggested movement<->document matches.

    The system auto-reconciles matches with confidence >= 0.95; everything
    below is a suggestion to confirm (reconcile_movement) or dismiss.
    """
    return get_client().get("/reconciliation/board")


@tool
def reconcile_movement(movement_id: str, document_id: str) -> Any:
    """Manually match a bank movement to an invoice/purchase document.

    Args:
        movement_id: bank movement UUID.
        document_id: invoice or purchase UUID.
    """
    return get_client().post(
        "/reconciliation/manual-match",
        json={"movement_id": movement_id, "document_id": document_id},
    )


# ===========================================================================
# Accounting & tax
# ===========================================================================
@tool
def list_accounts(
    search: str | None = None,
    group: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """List the Spanish PGC chart of accounts (code, name, UUID, balance).

    Use this to resolve an account's UUID for `ledger`, or to browse by
    `group` (1-7, the leading PGC digit: 5 = financial accounts, 4 =
    receivables/payables, …) or free-text `search` (code or name).
    """
    return get_client().get(
        "/accounts", search=search, group=group, limit=limit, offset=offset
    )


@tool
def ledger(
    account_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """Read ledger movements for ONE PGC account.

    Args:
        account_id: the account's UUID (required). Resolve it from
            list_accounts — e.g. find the account whose code is '572'
            (bancos) and pass its id here.
        from_date / to_date: ISO date bounds.
    """
    return get_client().get(
        "/ledger",
        account_id=account_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@tool
def trial_balance(at_date: str | None = None) -> Any:
    """Balance de sumas y saldos (trial balance) across every account.

    A one-shot overview of all account balances — no account_id needed.

    Args:
        at_date: ISO date to compute balances as of (default: today).
    """
    return get_client().get("/ledger/trial-balance", at_date=at_date)


@tool
def modelo_303_summary() -> Any:
    """Modelo 303 (quarterly VAT) — JSON summary of every quarter with activity.

    One row per (year, quarter): sales base, output VAT, rectified VAT,
    input VAT, and the net amount to pay. Use this for a machine-readable
    overview; use modelo_303_csv for the AEAT-format file of one quarter.
    """
    return get_client().get("/aeat/303/summary")


@tool
def modelo_303_csv(year: int, quarter: int) -> str:
    """Modelo 303 backing detail for one quarter as CSV text.

    Returns the per-transaction breakdown (one row per invoice/purchase line:
    date, doc, contact, base, rate, iva, input/output) that the quarter's VAT
    figures are built from — useful for auditing the numbers. For the
    aggregated box totals, use modelo_303_summary.

    Args:
        year: e.g. 2026.
        quarter: 1-4.
    """
    return get_client().get_text("/aeat/303", year=year, quarter=quarter)


# ===========================================================================
# Escape hatch
# ===========================================================================
@tool
def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Call any Aikount API endpoint not covered by a dedicated tool.

    The full surface is documented at https://api.aikount.com/openapi.json —
    fetch it (e.g. api_request('GET', '/../openapi.json')) when you need an
    endpoint this server doesn't wrap.

    Args:
        method: GET / POST / PATCH / DELETE.
        path: API path relative to the base, e.g. '/invoices' or
              '/contacts/<uuid>'. Leading slash optional.
        params: query parameters.
        body: JSON body (for POST/PATCH).
    """
    method = method.upper()
    if not path.startswith("/"):
        path = "/" + path
    c = get_client()
    if method == "GET":
        return c.get(path, **(params or {}))
    if method == "POST":
        return c.post(path, json=body, **(params or {}))
    if method == "PATCH":
        return c.patch(path, json=body)
    if method == "DELETE":
        return c.delete(path)
    return {"error": True, "detail": f"Unsupported method: {method}"}


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run(transport=os.environ.get("AIKOUNT_MCP_TRANSPORT", "stdio"))


if __name__ == "__main__":
    main()
