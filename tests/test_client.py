"""Unit tests for AikountClient — no network, httpx.MockTransport only."""

import httpx
import pytest

from aikount_mcp.client import AikountClient, AikountConfigError, AikountError


def make_client(handler):
    return AikountClient(token="agl_test", transport=httpx.MockTransport(handler))


def test_requires_token():
    with pytest.raises(AikountConfigError):
        AikountClient(token="")


def test_base_url_default_and_override():
    c = make_client(lambda r: httpx.Response(200, json={}))
    assert c.base_url == "https://api.aikount.com/api/v1"
    c2 = AikountClient(
        token="agl_test",
        base_url="http://localhost:8000/api/v1/",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    assert c2.base_url == "http://localhost:8000/api/v1"  # trailing slash stripped


def test_bearer_header_attached():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    make_client(handler).get("/auth/me")
    assert seen["auth"] == "Bearer agl_test"


def test_get_drops_none_params():
    def handler(request):
        # search omitted -> only limit survives
        assert "search" not in request.url.params
        assert request.url.params["limit"] == "50"
        return httpx.Response(200, json=[])

    make_client(handler).get("/contacts", search=None, limit=50)


def test_error_surfaces_detail():
    def handler(request):
        return httpx.Response(401, json={"detail": "token revoked"})

    with pytest.raises(AikountError) as ei:
        make_client(handler).get("/auth/me")
    assert ei.value.status_code == 401
    assert ei.value.detail == "token revoked"


def test_204_returns_ok():
    def handler(request):
        return httpx.Response(204)

    assert make_client(handler).delete("/x") == {"ok": True, "status_code": 204}


def test_post_file_multipart():
    captured = {}

    def handler(request):
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content
        return httpx.Response(200, json={"job_id": "j1", "status": "queued"})

    out = make_client(handler).post_file(
        "/ai/ingest-purchase",
        filename="factura.pdf",
        content=b"%PDF-1.4 fake",
        mime="application/pdf",
        fields={"force": False},
    )
    assert out["job_id"] == "j1"
    assert "multipart/form-data" in captured["content_type"]
    assert b"%PDF-1.4 fake" in captured["body"]
    assert b"force" in captured["body"]
