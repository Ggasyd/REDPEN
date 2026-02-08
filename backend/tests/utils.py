"""Test HTTP client utilities with an async-compatible wrapper."""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse


@dataclass
class ASGITransport:
    """Minimal ASGI transport holder for test client compatibility."""

    app: Any


class Response:
    """Minimal response object for tests."""

    def __init__(self, status_code: int, headers: dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = body

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


class AsyncClient:
    """Async ASGI test client without external dependencies."""

    def __init__(self, *, transport: ASGITransport, base_url: str = "http://test"):
        self._app = transport.app
        self._base_url = base_url.rstrip("/")

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def request(self, method: str, url: str, **kwargs) -> Response:
        headers = kwargs.pop("headers", {}) or {}
        params = kwargs.pop("params", None)
        json_payload = kwargs.pop("json", None)
        data = kwargs.pop("data", None)
        files = kwargs.pop("files", None)

        full_url = f"{self._base_url}{url}"
        if params:
            full_url = f"{full_url}?{urlencode(params)}"

        body, content_type = _encode_body(json_payload=json_payload, data=data, files=files)
        if content_type and "content-type" not in {k.lower() for k in headers}:
            headers = {**headers, "Content-Type": content_type}

        scope = _build_scope(method, full_url, headers)
        status_code, response_headers, response_body = await _call_asgi(
            self._app, scope, body
        )
        return Response(status_code, response_headers, response_body)

    async def get(self, url: str, **kwargs) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> Response:
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> Response:
        return await self.request("PATCH", url, **kwargs)


def _build_scope(method: str, full_url: str, headers: dict[str, str]) -> dict[str, Any]:
    parsed = urlparse(full_url)
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in headers.items()
    ]
    return {
        "type": "http",
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": parsed.scheme or "http",
        "path": parsed.path,
        "query_string": parsed.query.encode("latin-1"),
        "headers": raw_headers,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }


def _encode_body(
    *, json_payload: Any, data: dict[str, Any] | None, files: dict[str, Any] | None
) -> tuple[bytes, str | None]:
    if json_payload is not None:
        return json.dumps(json_payload).encode("utf-8"), "application/json"
    if files:
        return _encode_multipart(data or {}, files)
    if data:
        return urlencode(data).encode("utf-8"), "application/x-www-form-urlencoded"
    return b"", None


def _encode_multipart(
    data: dict[str, Any], files: dict[str, Any]
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    lines: list[bytes] = []

    def add_line(value: str) -> None:
        lines.append(value.encode("utf-8"))

    for key, value in data.items():
        add_line(f"--{boundary}")
        add_line(f'Content-Disposition: form-data; name="{key}"')
        add_line("")
        add_line(str(value))

    for field, file_info in files.items():
        filename, file_bytes, content_type = file_info
        add_line(f"--{boundary}")
        add_line(
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"'
        )
        add_line(f"Content-Type: {content_type}")
        add_line("")
        lines.append(file_bytes)

    add_line(f"--{boundary}--")
    add_line("")

    body = b"\r\n".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


async def _call_asgi(app: Any, scope: dict[str, Any], body: bytes):
    response_status = 500
    response_headers: dict[str, str] = {}
    response_body_chunks: list[bytes] = []
    receive_queue = asyncio.Queue()
    await receive_queue.put(
        {"type": "http.request", "body": body, "more_body": False}
    )

    async def receive():
        return await receive_queue.get()

    async def send(message: dict[str, Any]):
        nonlocal response_status, response_headers
        if message["type"] == "http.response.start":
            response_status = message["status"]
            response_headers = {
                key.decode("latin-1"): value.decode("latin-1")
                for key, value in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            response_body_chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return response_status, response_headers, b"".join(response_body_chunks)
