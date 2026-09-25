"""Watchlists (REST, auth required).

Captured flows::

    GET /v1/watchlist/read?sortBy=custom
    -> {"success":true,"data":{"watchlist1":[...symbol rows...],
        "watchlist2":..., "watchlist3":..., "watchlist4":..., "watchlist5":...}}

    POST /v1/watchlist/create
    body: {"symbol":"HBL","watchlist":"1","status":false}
    -> {"success":true,"data":"Watchlist updated"}

Note ``status`` is the add/remove switch: ``true`` adds the symbol to the
watchlist, ``false`` removes it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .config import API_BASE, CONTENT_TYPE, WATCHLIST
from .utils import TokenStore, DEFAULT_TOKEN_PATH


class WatchlistClient:
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

    def read(self, sort_by: str = "custom") -> Dict[str, List[Dict[str, Any]]]:
        """All watchlists keyed by name (``watchlist1`` .. ``watchlist5``)."""
        resp = self.session.get(
            API_BASE + WATCHLIST["read"], params={"sortBy": sort_by},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or data.get("Data") or {}

    def create(
        self, symbol: str, watchlist: Any = 1, status: bool = False
    ) -> Dict[str, Any]:
        """Add/remove ``symbol`` in a watchlist.

        ``status`` true adds, false removes (captured body used ``false``).
        """
        resp = self.session.post(
            API_BASE + WATCHLIST["create"],
            json={"symbol": symbol, "watchlist": str(watchlist), "status": status},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()
