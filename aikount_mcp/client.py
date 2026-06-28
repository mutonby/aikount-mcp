"""Thin HTTP client around the Aikount REST API.

The API is the source of truth; this client is a typed-ish wrapper that
attaches the bearer token, normalises errors, and parses JSON. Paths are
given relative to the API base (``/contacts``, ``/invoices/{id}/issue`` …),
which defaults to ``https://api.aikount.com/api/v1`` and can be overridden
via ``AIKOUNT_API`` for staging/self-hosted backends.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_API = "https://api.aikount.com/api/v1"
DEFAULT_TIMEOUT = 60.0


class AikountError(RuntimeError):
    """A 4xx/5xx response from the Aikount API.

    Carries the HTTP status and the API's ``{"detail": ...}`` payload so the
    MCP layer can surface something actionable instead of a raw stack trace.
    """

    def __init__(self, status_code: int, detail: Any, method: str, path: str):
        self.status_code = status_code
        self.detail = detail
        self.method = method
        self.path = path
        super().__init__(f"{method} {path} -> {status_code}: {detail}")


class AikountConfigError(RuntimeError):
    """Missing/invalid configuration (e.g. no API token)."""


class AikountClient:
    """Synchronous client. One instance per process is fine."""

    def __init__(
        self,
        token: str,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ):
        if not token:
            raise AikountConfigError(
                "No API token. Export AIKOUNT_TOKEN with an 'agl_...' key "
                "(mint one from the web app's 'Conectar agente' button)."
            )
        self.base_url = (base_url or DEFAULT_API).rstrip("/")
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "aikount-mcp/0.1",
            },
            timeout=timeout,
            transport=transport,
        )

    # -- low level ---------------------------------------------------------
    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        # Drop None query params so optional filters don't leak as "None".
        clean_params = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        resp = self._http.request(
            method,
            path,
            params=clean_params,
            json=json,
            files=files,
            data=data,
        )
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise AikountError(resp.status_code, detail, method, path)
        return resp

    @staticmethod
    def _parse(resp: httpx.Response) -> Any:
        if resp.status_code == 204 or not resp.content:
            return {"ok": True, "status_code": resp.status_code}
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.text

    # -- verbs -------------------------------------------------------------
    def get(self, path: str, **params: Any) -> Any:
        return self._parse(self._send("GET", path, params=params))

    def get_text(self, path: str, **params: Any) -> str:
        resp = self._send("GET", path, params=params)
        return resp.text

    def post(self, path: str, json: Any | None = None, **params: Any) -> Any:
        return self._parse(self._send("POST", path, params=params, json=json))

    def patch(self, path: str, json: Any | None = None) -> Any:
        return self._parse(self._send("PATCH", path, json=json))

    def delete(self, path: str) -> Any:
        return self._parse(self._send("DELETE", path))

    def post_file(
        self,
        path: str,
        filename: str,
        content: bytes,
        mime: str = "application/octet-stream",
        fields: dict[str, Any] | None = None,
    ) -> Any:
        files = {"file": (filename, content, mime)}
        data = {k: str(v) for k, v in (fields or {}).items()}
        return self._parse(self._send("POST", path, files=files, data=data))

    def close(self) -> None:
        self._http.close()


def client_from_env(transport: httpx.BaseTransport | None = None) -> AikountClient:
    """Build a client from AIKOUNT_TOKEN / AIKOUNT_API env vars."""
    return AikountClient(
        token=os.environ.get("AIKOUNT_TOKEN", ""),
        base_url=os.environ.get("AIKOUNT_API"),
        transport=transport,
    )
