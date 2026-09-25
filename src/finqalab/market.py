"""Market data via the public REST API.

Request shapes match the capture (``finqalab.db``). Unlike the earlier
draft, **all** snapshot endpoints are GETs:

* ``GET /v1/marketSnapshot/summaryV2`` (auth token) -> ``{"message": [...]}``
* ``GET /v1/snapshot/index_news``       -> ``{"data": {"index": [...]}}``
* ``GET /v1/snapshot/detail/statistics?symbol=X&date=DD-MM-YYYY``
* ``GET /v1/snapshot/detail/company?symbol=X``
* ``GET /v1/snapshot/detail/financial?symbol=X``
* ``GET /v1/snapshot/detail/graph?symbol=X&count=1&type=d&date=YYYY-MM-DD``
* ``GET /v1/news?page=0&type=0``        -> ``{"data": [...]}``

``summaryV2`` returns **every** symbol in one payload (no pagination params
in the capture), under the ``message`` key.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

import requests

from .config import API_BASE, MARKET
from .models import NewsItem, Snapshot
from .utils import TokenStore, DEFAULT_TOKEN_PATH


class MarketClient:
    def __init__(
        self,
        token: Optional[str] = None,
        session: Optional[requests.Session] = None,
        token_path: Optional[str] = DEFAULT_TOKEN_PATH,
    ):
        self._store = TokenStore(token_path)
        self.token = token or self._store.load()
        self.session = session or requests.Session()
        self.session.headers.update({"accept": "application/json"})

    def save_token(self) -> None:
        self._store.save(self.token)

    def clear_token(self) -> None:
        self.token = None
        self._store.clear()

    def _headers(self) -> dict:
        headers = {}
        if self.token:
            headers["x-auth-token"] = self.token
        return headers

    def _get(self, path: str, params: Optional[dict] = None) -> Dict[str, Any]:
        resp = self.session.get(API_BASE + path, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------- summary
    def summary(self, **params) -> Dict[str, Any]:
        """Raw ``summaryV2`` payload (``{"message": [...]}``).

        The capture sends no query params; pass ``sector=`` / ``page=`` if a
        newer app build supports them.
        """
        return self._get(MARKET["summary_v2"], params=params or None)

    def snapshots(self, **params) -> List[Snapshot]:
        """Parsed symbol list from the ``message`` key of ``summaryV2``."""
        data = self.summary(**params)
        raw = data.get("message") or data.get("data") or data.get("Data") or []
        if isinstance(raw, dict):
            raw = raw.get("list") or raw.get("rows") or []
        return [Snapshot.from_dict(item) for item in raw]

    # ------------------------------------------------------------------ index
    def index_news(self) -> Dict[str, Any]:
        """Index level / turnover for KSE100, KSE30, ALLSHR, ..."""
        return self._get(MARKET["index_news"])

    # ------------------------------------------------------------------ news
    def news(self, page: int = 0, news_type: int = 0) -> List[NewsItem]:
        """Paginated headlines. ``news_type`` 0-3 (feed category, see capture)."""
        data = self._get(MARKET["news"], {"page": page, "type": news_type})
        raw = data.get("data") or data.get("news") or data.get("Data") or []
        return [NewsItem.from_dict(item) for item in raw]

    # ------------------------------------------------------- snapshot details
    def statistics(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Price/volume bands + fundamentals. ``date`` is ``DD-MM-YYYY``."""
        params = {"symbol": symbol}
        if date is None:
            date = datetime.date.today().strftime("%d-%m-%Y")
        params["date"] = date
        return self._get(MARKET["statistics"], params)

    def company(self, symbol: str) -> Dict[str, Any]:
        """Company profile: description, registrar, people."""
        return self._get(MARKET["company"], {"symbol": symbol})

    def financial(self, symbol: str) -> Dict[str, Any]:
        """Quarterly / annual financial statements."""
        return self._get(MARKET["financial"], {"symbol": symbol})

    def graph(
        self,
        symbol: str,
        count: int = 1,
        interval: str = "d",
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Price/volume series. ``interval`` is ``d`` (day) or ``w`` (week);
        ``date`` is ``YYYY-MM-DD`` (defaults to today)."""
        if date is None:
            date = datetime.date.today().strftime("%Y-%m-%d")
        return self._get(
            MARKET["graph"],
            {"symbol": symbol, "count": count, "type": interval, "date": date},
        )
