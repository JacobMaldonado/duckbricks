"""Reverse-proxy routes for the internal Marimo service."""

import asyncio
import logging

import httpx
import websockets
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from websockets.asyncio.client import ClientConnection as WsClientConnection

from app.config import MARIMO_INTERNAL_URL

_logger = logging.getLogger(__name__)

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

_HEADERS_DROPPED_FROM_REQUEST = frozenset(["host", "accept-encoding"])
_HEADERS_DROPPED_FROM_RESPONSE = frozenset(["content-encoding", "content-length"])


def strip_hop_by_hop(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}


async def proxy_http_request(path: str, request: Request) -> Response:
    """Forward an HTTP request to the internal Marimo service."""
    target_url = f"{MARIMO_INTERNAL_URL}/marimo/{path}"
    query_string = request.url.query
    if query_string:
        target_url = f"{target_url}?{query_string}"

    forwarded_headers = strip_hop_by_hop(dict(request.headers))
    for header in _HEADERS_DROPPED_FROM_REQUEST:
        forwarded_headers.pop(header, None)

    _logger.debug("HTTP proxy: %s %s", request.method, target_url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        body = await request.body()
        backend_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forwarded_headers,
            content=body,
        )

    _logger.debug("HTTP proxy: response %d for %s", backend_response.status_code, target_url)

    response_headers = strip_hop_by_hop(dict(backend_response.headers))
    for header in _HEADERS_DROPPED_FROM_RESPONSE:
        response_headers.pop(header, None)

    return Response(
        content=backend_response.content,
        status_code=backend_response.status_code,
        headers=response_headers,
    )


async def _forward_client_to_backend(
    client_ws: WebSocket,
    backend_ws: WsClientConnection,
) -> None:
    """Forward messages from the browser WebSocket to the Marimo backend."""
    try:
        while True:
            message = await client_ws.receive()
            if message["type"] == "websocket.disconnect":
                _logger.debug("WS proxy: client disconnected normally")
                return
            if "bytes" in message and message["bytes"] is not None:
                await backend_ws.send(message["bytes"])
            elif "text" in message and message["text"] is not None:
                await backend_ws.send(message["text"])
    except WebSocketDisconnect:
        _logger.debug("WS proxy: WebSocketDisconnect on client receive")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _logger.warning("WS proxy: client→backend error: %s", exc)


async def _forward_backend_to_client(
    backend_ws: WsClientConnection,
    client_ws: WebSocket,
) -> None:
    """Forward messages from the Marimo backend to the browser WebSocket."""
    try:
        async for message in backend_ws:
            if isinstance(message, bytes):
                await client_ws.send_bytes(message)
            else:
                await client_ws.send_text(message)
    except WebSocketDisconnect:
        _logger.debug("WS proxy: WebSocketDisconnect sending to client")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _logger.warning("WS proxy: backend→client error: %s", exc)


async def proxy_websocket(client_ws: WebSocket, path: str = "ws") -> None:
    """Bidirectionally bridge a WebSocket connection to the internal Marimo service.

    Uses asyncio.wait(FIRST_COMPLETED) so that when either side closes the
    connection, the other task is cancelled immediately.  This prevents the
    proxy from hanging when the Marimo kernel restarts (common in sandbox mode),
    which was the root cause of 'Failed to sync document' errors.
    """
    await client_ws.accept()
    query_string = client_ws.scope.get("query_string", b"").decode()
    backend_uri = f"{MARIMO_INTERNAL_URL.replace('http', 'ws', 1)}/marimo/{path}"
    if query_string:
        backend_uri = f"{backend_uri}?{query_string}"

    extra_headers: dict[str, str] = {}
    cookie = client_ws.headers.get("cookie")
    if cookie:
        extra_headers["cookie"] = cookie

    _logger.info("WS proxy: connecting path=%s -> %s", path, backend_uri)

    try:
        async with websockets.connect(backend_uri, additional_headers=extra_headers) as backend_ws:
            _logger.debug("WS proxy: backend connected for path=%s", path)

            to_backend = asyncio.ensure_future(_forward_client_to_backend(client_ws, backend_ws))
            to_client = asyncio.ensure_future(_forward_backend_to_client(backend_ws, client_ws))

            _done, pending = await asyncio.wait(
                {to_backend, to_client},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            _logger.debug("WS proxy: session ended for path=%s", path)
    except Exception as exc:
        _logger.warning("WS proxy: connection error for %s: %s", backend_uri, exc)
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
