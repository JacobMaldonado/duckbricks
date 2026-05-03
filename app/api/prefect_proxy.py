"""Reverse-proxy routes for the Prefect server UI and API."""

import logging

import httpx
from fastapi import Request
from fastapi.responses import Response

from app.config import PREFECT_INTERNAL_URL

_log = logging.getLogger(__name__)

_HOP_BY_HOP_HEADERS = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    ]
)
_REQUEST_HEADERS_DROPPED = frozenset(["host", "accept-encoding"])
_RESPONSE_HEADERS_DROPPED = frozenset(
    [
        "content-encoding",
        "content-length",
        "x-frame-options",
        "content-security-policy",
    ]
)


def _strip_hop_by_hop(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}


async def proxy_prefect_http(path: str, request: Request) -> Response:
    """Forward an HTTP request to the internal Prefect server.

    The proxy is mounted at /prefect-ui/{path}. Because PREFECT_UI_SERVE_BASE
    is set to /prefect-ui on the Prefect server, the target URL must also
    include the /prefect-ui prefix so the paths align correctly.
    """
    target_url = f"{PREFECT_INTERNAL_URL}/prefect-ui/{path}"
    query_string = request.url.query
    if query_string:
        target_url = f"{target_url}?{query_string}"

    forwarded_headers = _strip_hop_by_hop(dict(request.headers))
    for header in _REQUEST_HEADERS_DROPPED:
        forwarded_headers.pop(header, None)

    _log.debug("Prefect proxy: %s %s", request.method, target_url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        body = await request.body()
        backend_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forwarded_headers,
            content=body,
        )

    _log.debug("Prefect proxy: %d for %s", backend_response.status_code, target_url)

    response_headers = _strip_hop_by_hop(dict(backend_response.headers))
    for header in _RESPONSE_HEADERS_DROPPED:
        response_headers.pop(header, None)

    return Response(
        content=backend_response.content,
        status_code=backend_response.status_code,
        headers=response_headers,
    )
