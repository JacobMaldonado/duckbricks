"""Reverse-proxy routes for the internal Marimo service."""

import asyncio

import httpx
import websockets
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.config import MARIMO_INTERNAL_URL

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


def strip_hop_by_hop(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}


async def proxy_http_request(path: str, request: Request) -> Response:
    """Forward an HTTP request to the internal Marimo service."""
    target_url = f"{MARIMO_INTERNAL_URL}/marimo/{path}"
    query_string = request.url.query
    if query_string:
        target_url = f"{target_url}?{query_string}"

    forwarded_headers = strip_hop_by_hop(dict(request.headers))
    forwarded_headers.pop("host", None)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        body = await request.body()
        backend_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forwarded_headers,
            content=body,
        )

    response_headers = strip_hop_by_hop(dict(backend_response.headers))
    return Response(
        content=backend_response.content,
        status_code=backend_response.status_code,
        headers=response_headers,
    )


async def proxy_websocket(client_ws: WebSocket) -> None:
    """Bidirectionally bridge a WebSocket connection to the internal Marimo service."""
    await client_ws.accept()
    query_string = client_ws.scope.get("query_string", b"").decode()
    backend_uri = f"{MARIMO_INTERNAL_URL.replace('http', 'ws', 1)}/marimo/ws"
    if query_string:
        backend_uri = f"{backend_uri}?{query_string}"

    try:
        async with websockets.connect(backend_uri) as backend_ws:

            async def forward_to_backend() -> None:
                try:
                    while True:
                        message = await client_ws.receive()
                        if message["type"] == "websocket.disconnect":
                            break
                        if "bytes" in message and message["bytes"] is not None:
                            await backend_ws.send(message["bytes"])
                        elif "text" in message and message["text"] is not None:
                            await backend_ws.send(message["text"])
                except (WebSocketDisconnect, Exception):
                    pass

            async def forward_to_client() -> None:
                try:
                    async for message in backend_ws:
                        if isinstance(message, bytes):
                            await client_ws.send_bytes(message)
                        else:
                            await client_ws.send_text(message)
                except (WebSocketDisconnect, Exception):
                    pass

            await asyncio.gather(forward_to_backend(), forward_to_client())
    except Exception:
        pass
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
