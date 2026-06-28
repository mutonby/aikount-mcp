"""Tests for the MCP tool wrappers — verify each hits the REAL verified path.

These guard against regressing back to the stale skill paths (the published
SKILL.md / llms.txt document several wrong routes, e.g. /banking/treasuries,
/reconciliation/match, /tax/aeat-303). We assert the tools call the routes
that actually exist in the OpenAPI spec.
"""

import httpx
import pytest

from aikount_mcp import server
from aikount_mcp.client import AikountClient


@pytest.fixture
def record(monkeypatch):
    """Install a mock client and capture (method, path, params, json/body)."""
    calls = []

    def handler(request):
        calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "body": request.content.decode() if request.content else "",
            }
        )
        # Return shape-agnostic success; ledger/303 csv read text.
        if request.url.path.endswith("/aeat/303"):
            return httpx.Response(200, text="HEADER;1;2;3", headers={"content-type": "text/csv"})
        return httpx.Response(200, json={"ok": True})

    client = AikountClient(token="agl_test", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(server, "_client", client)
    return calls


def last(calls):
    return calls[-1]


def test_whoami_uses_tenants_me(record):
    # /auth/me rejects API keys (onboarding-only); whoami reads /tenants/me.
    server.whoami()
    assert last(record)["method"] == "GET"
    assert last(record)["path"] == "/api/v1/tenants/me"


def test_ledger_requires_account_id(record):
    server.ledger(account_id="acc-1", from_date="2026-01-01")
    c = last(record)
    assert c["path"] == "/api/v1/ledger"
    assert c["params"]["account_id"] == "acc-1"  # NOT 'account'


def test_list_accounts_path(record):
    server.list_accounts(group=5)
    c = last(record)
    assert c["path"] == "/api/v1/accounts"
    assert c["params"]["group"] == "5"


def test_trial_balance_path(record):
    server.trial_balance()
    assert last(record)["path"] == "/api/v1/ledger/trial-balance"


def test_list_contacts_uses_search_param(record):
    server.list_contacts(search="acme", kind="customer")
    c = last(record)
    assert c["path"] == "/api/v1/contacts"
    assert c["params"]["search"] == "acme"  # NOT 'q'
    assert c["params"]["kind"] == "customer"


def test_list_treasuries_real_path(record):
    server.list_treasuries()
    assert last(record)["path"] == "/api/v1/treasuries"  # NOT /banking/treasuries


def test_list_bank_movements_real_path(record):
    server.list_bank_movements(treasury_id="t1", status="unreconciled")
    c = last(record)
    assert c["path"] == "/api/v1/bank-movements"  # NOT /banking/movements
    assert c["params"]["treasury_id"] == "t1"


def test_reconcile_movement_real_path_and_body(record):
    server.reconcile_movement(movement_id="m1", document_id="d1")
    c = last(record)
    assert c["path"] == "/api/v1/reconciliation/manual-match"  # NOT /reconciliation/match
    assert '"movement_id":"m1"' in c["body"]
    assert '"document_id":"d1"' in c["body"]  # NOT 'doc_id'


def test_create_invoice_body(record):
    server.create_invoice(
        contact_id="c1",
        doc_date="2026-05-21",
        lines=[{"description": "Consultoría", "quantity": 1, "unit_price": 1200.0}],
    )
    c = last(record)
    assert c["method"] == "POST"
    assert c["path"] == "/api/v1/invoices"
    assert '"unit_price":1200.0' in c["body"]  # euros, not cents
    assert '"contact_id":"c1"' in c["body"]


def test_issue_invoice_path(record):
    server.issue_invoice("inv-1")
    assert last(record)["path"] == "/api/v1/invoices/inv-1/issue"


def test_modelo_303_summary_path(record):
    server.modelo_303_summary()
    assert last(record)["path"] == "/api/v1/aeat/303/summary"  # NOT /tax/aeat-303


def test_modelo_303_csv_returns_text(record):
    out = server.modelo_303_csv(2026, 2)
    assert isinstance(out, str) and out.startswith("HEADER")
    c = last(record)
    assert c["path"] == "/api/v1/aeat/303"
    assert c["params"]["year"] == "2026" and c["params"]["quarter"] == "2"


def test_list_tax_types_path(record):
    server.list_tax_types()
    assert last(record)["path"] == "/api/v1/taxes"


def test_api_request_normalises_leading_slash(record):
    server.api_request("GET", "ledger/trial-balance")
    assert last(record)["path"] == "/api/v1/ledger/trial-balance"


def test_error_returned_as_data(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"detail": "token revoked"})

    client = AikountClient(token="agl_test", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(server, "_client", client)
    out = server.whoami()
    assert out["error"] is True
    assert out["status_code"] == 401
    assert "Re-run" in out["hint"]


def test_no_create_purchase_tool():
    """Purchases must go through the deduped ingest path, never a raw create."""
    assert not hasattr(server, "create_purchase")
