"""Price/event alert permissions + history (REST, auth required).

Captured flows::

    GET /v1/alert_permission/byUserId
    -> {"data":[{"symbol":"MZNPETF","defaultEvents":[],"customEvents":[]}, ...]}

    GET /v1/alert_permission/history
    -> {"data":[{"user_id","symbol","title","type","target","alertType",
                 "date","timestamp","data":{...notification...}}, ...]}

    POST /v1/alert_permission            (create / toggle an alert)
    body: {"symbol":"OGDC","notificationType":0,"alertType":2,
           "target":"15","isDefault":false,"isRecurring":true}
    -> the server generates the human-readable ``title`` itself, e.g.
       "Rises over 15"; do not send one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .config import ALERTS, API_BASE, CONTENT_TYPE
from .utils import TokenStore, DEFAULT_TOKEN_PATH


class AlertsClient:
    def __init__(
        self,
        token: Optional[str] = None,
        session: Optional[requests.Session] = None,
        token_path: Optional[str] = DEFAULT_TOKEN_PATH,
    ):
        self._store = TokenStore(token_path)
        self.token = token or self._store.load()
        self.session = session or requests.Session()

    def save_token(self) -> None:
        self._store.save(self.token)

    def clear_token(self) -> None:
        self.token = None
        self._store.clear()

    def _headers(self) -> dict:
        headers = {"content-type": CONTENT_TYPE}
        if self.token:
            headers["x-auth-token"] = self.token
            headers["cookie"] = f"xauth={self.token}"
        return headers

    def _get(self, path: str) -> Dict[str, Any]:
        resp = self.session.get(API_BASE + path, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def by_user_id(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Per-symbol alert subscriptions (default + custom events).

        Pass ``symbol`` to scope the response to one instrument.
        """
        params = {"symbol": symbol} if symbol else None
        resp = self.session.get(
            API_BASE + ALERTS["by_user_id"], params=params, headers=self._headers()
        )
        resp.raise_for_status()
        return resp.json().get("data") or []

    def history(self) -> List[Dict[str, Any]]:
        """Delivered alert notifications."""
        return self._get(ALERTS["history"]).get("data") or []

    def create(
        self,
        symbol: str,
        notification_type: int = 0,
        alert_type: int = 2,
        target: str = "15",
        is_recurring: bool = True,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """Create or update a price alert.

        ``alert_type`` 2 is a percentage move and ``target`` is the
        threshold. The server derives the ``title``, so it is not sent.
        """
        resp = self.session.post(
            API_BASE + ALERTS["create"],
            json={
                "symbol": symbol,
                "notificationType": notification_type,
                "alertType": alert_type,
                "target": str(target),
                "isDefault": is_default,
                "isRecurring": is_recurring,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()
