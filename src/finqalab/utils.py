"""Shared helpers: base64, JWT decode, device id, STOMP framing.

The app frames STOMP messages as ``json.dumps([frame])`` where ``frame``
is a normal string containing real ``\\n`` line breaks and a trailing NUL;
``json.dumps`` escapes those into ``\\n`` / ``\\u0000`` on the wire, which
is exactly what the capture shows.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any, Optional, Tuple


def b64decode(data: str) -> bytes:
    return base64.b64decode(data)


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def random_device_id() -> str:
    return os.urandom(8).hex()


def decode_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("not a JWT")
    pad = "=" * (-len(parts[1]) % 4)
    payload = base64.urlsafe_b64decode(parts[1] + pad)
    return json.loads(payload)


def jwt_expires(token: str) -> Optional[int]:
    try:
        return decode_jwt(token).get("exp")
    except Exception:
        return None


def frame_connect(client_code: str, nostr: str) -> str:
    return (
        "CONNECT\n"
        f"id:{client_code}\n"
        f"nostr:{nostr}\n"
        "accept-version:1.0,1.1,1.2\n"
        "heart-beat:5000,5000\n"
        "\n"
        "\x00"
    )


def frame_subscribe(destination: str, subscription_id: str) -> str:
    return f"SUBSCRIBE\ndestination:{destination}\nid:{subscription_id}\n\n\x00"


def frame_unsubscribe(subscription_id: str) -> str:
    return f"UNSUBSCRIBE\nid:{subscription_id}\n\n\x00"


def frame_send(destination: str, body: dict) -> str:
    payload = json.dumps(body, separators=(",", ":"))
    return (
        "SEND\n"
        f"destination:{destination}\n"
        f"content-length:{len(payload)}\n"
        "\n"
        f"{payload}"
        "\x00"
    )


def wire(frame: str) -> str:
    return json.dumps([frame])


class StompFrame:
    """Parsed STOMP frame: ``command``, ``headers``, ``body``."""

    __slots__ = ("command", "headers", "body")

    def __init__(self, command: str, headers: dict, body: str):
        self.command = command
        self.headers = headers
        self.body = body

    def json(self) -> Any:
        if not self.body:
            return None
        try:
            return json.loads(self.body)
        except json.JSONDecodeError:
            return self.body

    def __repr__(self) -> str:  # pragma: no cover
        return f"StompFrame({self.command!r}, {self.headers!r}, {self.body[:80]!r})"


def parse_frame(raw: str) -> StompFrame:
    """Parse a SockJS ``a["..."]`` (or plain ``"..."``) STOMP frame."""
    text = raw.strip()
    if text.startswith("o") or text == "h" or text.startswith("c["):
        raise ValueError(f"not a STOMP MESSAGE frame: {text[:40]!r}")
    if text.startswith("a"):
        text = text[1:]
    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"bad SockJS JSON: {text[:80]!r}")
    if not arr:
        raise ValueError("empty SockJS array")
    frame_str = arr[0]
    nul = frame_str.find("\x00")
    if nul != -1:
        frame_str = frame_str[:nul]
    head, _, body = frame_str.partition("\n\n")
    lines = head.split("\n")
    command = lines[0]
    headers: dict = {}
    for line in lines[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k] = v
    return StompFrame(command, headers, body)


def now_pkst_hhmm() -> str:
    """Local time formatted as HH:MM (the app uses this for order list bounds)."""
    import datetime

    now = datetime.datetime.now()
    return now.strftime("%H:%M")


def stamp() -> str:
    return str(int(time.time() * 1000))


DEFAULT_TOKEN_PATH = os.path.join(os.path.expanduser("~"), ".finqalab_token")


class TokenStore:
    """Shared disk-backed token persistence for all REST clients.

    Stores ``{"token": "...", "user_id": "..."}`` as JSON in a file.
    Pass ``token_path=None`` to disable persistence.
    """

    def __init__(self, token_path: Optional[str] = DEFAULT_TOKEN_PATH):
        self.token_path = token_path

    def load(self) -> Optional[str]:
        if self.token_path is None:
            return None
        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                return json.load(f).get("token")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def save(self, token: str, user_id: Optional[str] = None) -> None:
        if self.token_path is None or not token:
            return
        data = {"token": token}
        if user_id is not None:
            data["user_id"] = user_id
        with open(self.token_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def clear(self) -> None:
        if self.token_path is None:
            return
        try:
            os.remove(self.token_path)
        except FileNotFoundError:
            pass
