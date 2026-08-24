from __future__ import annotations

"""ASGI-level request body limits for endpoints that accept user input.

Route-level ``Content-Length`` checks are useful as an early rejection, but
they do not protect against chunked requests and happen too late for multipart
parsing.  This middleware counts ASGI chunks before Starlette buffers or parses
them, including ``UploadFile`` temporary-file handling.
"""

from collections.abc import Awaitable, Callable
from typing import Any


DEFAULT_BODY_LIMIT_BYTES = 1 * 1024 * 1024
# Keep the stream guard exactly aligned with the route-level webhook checks;
# otherwise a chunked body just above the provider limit would still be
# buffered before the route rejects it.
WEBHOOK_BODY_LIMIT_BYTES = 1_000_000
UPLOAD_BODY_LIMIT_BYTES = 5 * 1024 * 1024 + 128 * 1024

_WEBHOOK_PATHS = {"/api/stripe/webhook", "/api/paypal/webhook"}
# Public review uploads are intentionally not exposed.  Images can only be
# uploaded through the authenticated staff endpoint.
_UPLOAD_PATHS = {"/api/upload"}

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class RequestBodyTooLarge(Exception):
    pass


def get_request_body_limit(path: str) -> int:
    if path in _WEBHOOK_PATHS:
        return WEBHOOK_BODY_LIMIT_BYTES
    if path in _UPLOAD_PATHS:
        return UPLOAD_BODY_LIMIT_BYTES
    return DEFAULT_BODY_LIMIT_BYTES


def _content_length_exceeds(scope: Scope, limit: int) -> bool:
    headers = scope.get("headers") or []
    for raw_name, raw_value in headers:
        if raw_name.lower() != b"content-length":
            continue
        try:
            return int(raw_value) > limit
        except (TypeError, ValueError):
            return True
    return False


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = get_request_body_limit(str(scope.get("path") or ""))
        if _content_length_exceeds(scope, limit):
            await self._send_too_large(send)
            return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body") or b"")
                if received_bytes > limit:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            # None of the protected endpoints emits a response before reading
            # its request body. Avoid attempting a second response defensively.
            if not response_started:
                await self._send_too_large(send)

    @staticmethod
    async def _send_too_large(send: Send) -> None:
        body = b'{"detail":"Request body is too large."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
