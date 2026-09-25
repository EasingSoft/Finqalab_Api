"""Payments: deposits, withdrawals, bank accounts, cash reports.

Two kinds of reports:

* **JSON** (this module's focus): ``periodic_details()`` = all historical
  trades (stocks in/out) pulled over the STOMP
  ``periodicTradeDetailReportRequest`` channel; ``cashbook()`` = the cash
  flow ledger composed from the deposits (cash in) + withdrawals (cash out)
  REST endpoints.
* **PDF** (display-only, as the app uses them): ``periodic_pdf()`` and
  ``cashbook_pdf()`` return the generated documents the app opens in its
  PDF viewer; the app never reads JSON from those endpoints.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

import requests

from .config import API_BASE, CONTENT_TYPE, PAYMENTS
from .models import Trade
from .stomp import StompClient
from .utils import TokenStore, DEFAULT_TOKEN_PATH

_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def _iso(epoch_ms: Optional[Any]) -> Optional[str]:
    if epoch_ms in (None, "", 0):
        return None
    try:
        ms = int(epoch_ms)
    except (TypeError, ValueError):
        return str(epoch_ms)
    return (_EPOCH + datetime.timedelta(milliseconds=ms)).date().isoformat()


class PaymentsClient:
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

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.session.post(API_BASE + path, json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: Optional[dict] = None) -> Dict[str, Any]:
        resp = self.session.get(API_BASE + path, params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------- deposits
    def deposits_history(self) -> List[Dict[str, Any]]:
        """Raw deposit rows (cash in). ``data`` items look like
        ``{"id", "amount", "createdAt"(epoch ms), "status", "payment_method",
        "payment_status", ...}``."""
        data = self._get(PAYMENTS["deposits_history"])
        return data.get("data") or data.get("Data") or []

    # ------------------------------------------------------------ withdrawals
    def withdrawal_history(self) -> List[Dict[str, Any]]:
        """Raw withdrawal rows (cash out) from ``GET /v1/withdrawal``."""
        data = self._get(PAYMENTS["withdrawal"])
        return data.get("data") or data.get("Data") or []

    def get_bank_codes(self) -> List[Dict[str, Any]]:
        """``[{name, code}]`` bank list."""
        data = self._get(PAYMENTS["bank_code_list"])
        return data.get("data") or data.get("Data") or []

    def get_accounts(self) -> List[Dict[str, Any]]:
        """Registered beneficiary IBAN accounts."""
        data = self._get(PAYMENTS["accounts"])
        return data.get("data") or data.get("Data") or []

    def withdrawal(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Request a withdrawal with a hand-built ``body``.

        The request shape was never captured, so this is a raw passthrough
        rather than a typed wrapper. See
        ``doc/reverse/05-known-gaps.md`` for the V2 flow and its OTP step.
        """
        return self._post(PAYMENTS["withdrawal"], body)

    # ----------------------------------------------------------------- cash
    def cashbook(self) -> List[Dict[str, Any]]:
        """Normalized cash-flow ledger.

        Each row is ``{"date", "type" (DEPOSIT/WITHDRAWAL), "amount" (signed
        PKR), "method", "status"}``. Deposits are cash *in* (positive),
        withdrawals cash *out* (negative); the app composes this report the
        same way from the two history endpoints.
        """
        rows: List[Dict[str, Any]] = []
        for d in self.deposits_history():
            rows.append(
                {
                    "date": _iso(d.get("createdAt")),
                    "type": "DEPOSIT",
                    "amount": d.get("amount"),
                    "method": d.get("payment_method"),
                    "status": d.get("payment_status") or d.get("status"),
                }
            )
        for w in self.withdrawal_history():
            amount = w.get("amount")
            rows.append(
                {
                    "date": _iso(w.get("createdAt")),
                    "type": "WITHDRAWAL",
                    "amount": -amount if isinstance(amount, (int, float)) else amount,
                    "method": w.get("payment_method"),
                    "status": w.get("payment_status") or w.get("status"),
                }
            )
        rows.sort(key=lambda r: r["date"] or "")
        return rows

    # ---------------------------------------------------------------- trades
    def periodic_details(
        self,
        client_code: str,
        nostr: str,
        from_date: str,
        to_date: str,
        symbol: Optional[str] = None,
        oms_user_id: Optional[str] = None,
        session_token: Optional[str] = None,
        url: Optional[str] = None,
        timeout: float = 8.0,
    ) -> List[Trade]:
        """Periodic details report (stocks in/out) over STOMP.

        ``from_date`` / ``to_date`` are ``DD/MM/YYYY`` (captured:
        ``{"clientCode", "fromDate", "toDate", "symbol"}``). The app shows
        this as the historical trade report; each executed trade has
        ``buyQty`` / ``sellQty`` / ``rate`` / ``netAmount``.

        The server ignores date params and returns all historical trades,
        so client-side filtering is applied on ``trade_date`` (``YYYY-MM-DD``).
        """
        from .order.order_list import OrderListTimeout, _subscribe_and_send

        body: Dict[str, Any] = {
            "clientCode": client_code,
            "fromDate": from_date,
            "toDate": to_date,
        }
        if symbol is not None:
            body["symbol"] = symbol
        client = StompClient(
            client_code, nostr, oms_user_id=oms_user_id,
            session_token=session_token, url=url,
        )
        try:
            with client:
                data = _subscribe_and_send(
                    client, client_code, "periodicTradeDetailReportRequest", body, timeout
                )
        except Exception as exc:
            raise OrderListTimeout(str(exc))
        if isinstance(data, list):
            raw = data
        else:
            raw = data.get("TradeDetails") or data.get("tradeDetails") or data.get("Data") or []

        trades = [Trade.from_dict(item) for item in raw]

        # Server returns all historical trades; filter client-side.
        # Convert DD/MM/YYYY bounds to YYYY-MM-DD for comparison.
        try:
            fd = datetime.datetime.strptime(from_date, "%d/%m/%Y").strftime("%Y-%m-%d")
            td = datetime.datetime.strptime(to_date, "%d/%m/%Y").strftime("%Y-%m-%d")
            trades = [t for t in trades if t.trade_date and fd <= t.trade_date <= td]
        except ValueError:
            pass

        return trades

    # ------------------------------------------------------------------ pdfs
    def periodic_pdf(self, body: Dict[str, Any]) -> bytes:
        """Generate the periodic-details PDF (display only)."""
        resp = self.session.post(
            API_BASE + PAYMENTS["periodic_pdf"], json=body, headers=self._headers()
        )
        resp.raise_for_status()
        return resp.content

    def cashbook_pdf(self, body: Dict[str, Any]) -> bytes:
        """Generate the cashbook PDF (display only)."""
        resp = self.session.post(
            API_BASE + PAYMENTS["cashbook_pdf"], json=body, headers=self._headers()
        )
        resp.raise_for_status()
        return resp.content
