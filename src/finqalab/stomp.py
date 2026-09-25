"""STOMP 1.2 over SockJS trading WebSocket.

Mirrors the app's ``service/stomp_config.dart`` and the working
``order bot/orderbot.py``.

Connection::

    wss://trade.nextcapital.com.pk/order-dispatch-websocket/{oms_user_id}/{session_token}/websocket

Auth is in the STOMP ``CONNECT`` frame: ``id`` = client code, ``nostr`` =
websocket password (plaintext). No AES needed on this path.

Framing: client sends ``json.dumps([stomp_frame])`` (SockJS), server
answers ``a[...]`` for messages and ``h`` every ~25s as a heartbeat.

See :mod:`finqalab.order` and :mod:`finqalab.portfolio` for high-level
wrappers built on top of this client.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

from .config import WS_HOST, WS_SCHEME, WS_SESSION_OMS_USER_ID, WS_SESSION_TOKEN, WS_STOMP_ENDPOINT
from .utils import frame_connect, frame_send, frame_subscribe, frame_unsubscribe, parse_frame, wire


class StompError(Exception):
    """Raised on STOMP-level failures (CONNECT rejected, etc.)."""


class StompClient:
    """Synchronous STOMP client over a SockJS WebSocket."""

    def __init__(
        self,
        client_code: str,
        nostr: str,
        oms_user_id: Optional[str] = None,
        session_token: Optional[str] = None,
        url: Optional[str] = None,
        connect_timeout: float = 15.0,
    ):
        self.client_code = client_code
        self.nostr = nostr
        self.url = url or (
            f"{WS_SCHEME}://{WS_HOST}"
            + WS_STOMP_ENDPOINT.format(
                oms_user_id=oms_user_id or WS_SESSION_OMS_USER_ID,
                session_token=session_token or WS_SESSION_TOKEN,
            )
        )
        self.connect_timeout = connect_timeout
        self._ws = None
        self._sub_counter = 0

    def connect(self) -> "StompClient":
        """Open the socket and complete the STOMP handshake."""
        from websockets.sync.client import connect as ws_connect

        self._ws = ws_connect(self.url, open_timeout=self.connect_timeout)
        self.send_raw(wire(frame_connect(self.client_code, self.nostr)))
        deadline = time.time() + self.connect_timeout
        while time.time() < deadline:
            frame = self._next_frame()
            if frame is None:
                continue
            if frame.command == "CONNECTED":
                return self
            if frame.command == "ERROR":
                raise StompError(frame.headers.get("message", "CONNECT rejected"))
        raise StompError("timed out waiting for CONNECTED")

    def send_raw(self, message: str) -> None:
        if self._ws is None:
            raise StompError("not connected")
        self._ws.send(message)

    def subscribe_raw(self, destination: str, subscription_id: Optional[str] = None) -> str:
        """Subscribe to an explicit ``destination`` with a chosen id.

        The app passes explicit ids (e.g. the client code itself) on some
        channels (``periodicTradeDetailReportRequest``); both the id and the
        route must match what the SEND uses on the reply.
        """
        sub_id = subscription_id or f"sub-{self._sub_counter}"
        self._sub_counter += 1
        self.send_raw(wire(frame_subscribe(destination, sub_id)))
        return sub_id

    def subscribe(self, topic: str, subscription_id: Optional[str] = None) -> str:
        """Subscribe to ``/user/{client}/order-service/{topic}``."""
        return self.subscribe_raw(
            f"/user/{self.client_code}/order-service/{topic}", subscription_id
        )

    def unsubscribe(self, subscription_id: str) -> None:
        self.send_raw(wire(frame_unsubscribe(subscription_id)))

    def send_action(self, topic: str, body: Dict[str, Any]) -> None:
        """SEND to ``/app/order-service.{topic}.{client}`` (capture uses
        ``order-list.<client_code>``, ``portfolio.<client_code>``, ``periodicTradeDetailReportRequest.<client_code>``)."""
        dest = f"/app/order-service/{topic}.{self.client_code}"
        self.send_raw(wire(frame_send(dest, body)))

    def send(self, destination: str, body: Dict[str, Any]) -> None:
        """SEND to an explicit destination (e.g. ``/app/order-service.<client_code>``)."""
        self.send_raw(wire(frame_send(destination, body)))

    def _next_frame(self):
        msg = self._ws.recv()
        text = msg.decode() if isinstance(msg, bytes) else msg
        if text == "h" or text == "o":
            return None
        return parse_frame(text)

    def recv(self, timeout: Optional[float] = None) -> Tuple[Any, Any]:
        """Receive one message. Returns ``(headers, json_body)`` of the next
        ``MESSAGE`` frame; ``(None, None)`` on heartbeat frames."""
        import websockets.exceptions

        deadline = None if timeout is None else time.time() + timeout
        while True:
            try:
                remaining = None if deadline is None else deadline - time.time()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError("recv timed out")
                frame = self._next_frame()
            except TimeoutError:
                raise TimeoutError("recv timed out")
            except websockets.exceptions.ConnectionClosed:
                raise StompError("connection closed")
            if frame is None:
                continue
            if frame.command == "MESSAGE":
                return frame.headers, frame.json()
            if frame.command == "ERROR":
                raise StompError(frame.headers.get("message", "STOMP error"))

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def connect_from_env() -> "StompClient":
        """Build from ``FQ_CLIENT_CODE`` / ``FQ_NOSTR`` env vars."""
        import os

        code = os.environ["FQ_CLIENT_CODE"]
        nostr = os.environ["FQ_NOSTR"]
        return StompClient(code, nostr)
