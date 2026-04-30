"""Marimo startup wrapper that patches HTTPRequest user serialization.

In sandbox mode, Marimo spawns a subprocess per notebook and communicates
via IPC queues serialized with msgspec. Starlette's SimpleUser object
(used for anonymous sessions in --no-token mode) is not msgspec-encodable,
causing 'Encoding objects of type SimpleUser is unsupported'.

This wrapper converts any non-serializable user object to a plain dict
before it is stored in HTTPRequest, making IPC serialization transparent.
"""

from __future__ import annotations

import sys


def patch_http_request_user_serialization() -> None:
    """Ensure HTTPRequest.user is always a msgspec-encodable type."""
    from marimo._runtime.commands import HTTPRequest

    original = HTTPRequest.from_request

    def safe_from_request(request):  # type: ignore[no-untyped-def]
        http_request = original(request)
        user = http_request.user
        if not isinstance(user, dict | str | int | float | bool | list | type(None)):
            try:
                http_request.user = vars(user)
            except TypeError:
                http_request.user = {}
        return http_request

    HTTPRequest.from_request = staticmethod(safe_from_request)  # type: ignore[assignment]


if __name__ == "__main__":
    patch_http_request_user_serialization()
    from marimo.__main__ import main

    sys.exit(main())
