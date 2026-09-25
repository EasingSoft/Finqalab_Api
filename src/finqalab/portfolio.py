"""Portfolio and trade data over the trading WebSocket.

Capture::

    SEND /app/order-service/portfolio.<client_code>
    body: {"clientCode":"","sequenceId":"2101961833"}
    -> MESSAGE /user/<client_code>/order-service.portfolio        (bare JSON array)

    SEND /app/order-service/periodicTradeDetailReportRequest.<client_code>
    body: {"clientCode":"<client_code>","fromDate":"14/06/2026",
           "toDate":"13/08/2026","symbol":"FCEPL"}
    -> MESSAGE /user/<client_code>/order-service.periodicTradeDetailReportRequest
       (bare JSON array of executed trades)

Both responses are JSON arrays; ``sequenceId`` is a client-generated request
id (defaults to an epoch-ms stamp).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import Holding, Trade
from .stomp import StompClient
from .order.order_list import OrderListTimeout, _subscribe_and_send
from .utils import stamp

logger = logging.getLogger("finqalab.portfolio")


def portfolio(
    client_code: str,
    nostr: str,
    sequence_id: Optional[str] = None,
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
) -> List[Dict[str, Any]]:
    """Return the portfolio rows (holdings + cash + totals)."""
    body = {"clientCode": "", "sequenceId": sequence_id or stamp()}
    client = StompClient(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url,
    )
    try:
        with client:
            data = _subscribe_and_send(client, client_code, "portfolio", body, timeout)
    except Exception as exc:
        raise OrderListTimeout(str(exc))
    if isinstance(data, list):
        return data
    for key in ("HoldingDetails", "holdings", "HoldingList", "Data"):
        raw = data.get(key)
        if isinstance(raw, list):
            return raw
    return []


def holdings(
    client_code: str,
    nostr: str,
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
) -> List[Holding]:
    """Holdings rows from the portfolio payload."""
    rows = portfolio(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url, timeout=timeout,
    )
    return [Holding.from_dict(item) for item in rows]


def cash_balance(
    client_code: str,
    nostr: str,
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
) -> Any:
    """Cash balance (unblocked / total) from the cash row in the payload."""
    for row in portfolio(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url, timeout=timeout,
    ):
        if "cashBalance" in row or "CashBalance" in row:
            return row.get("cashBalance", row.get("CashBalance"))
        if "security" in row and "Money" in str(row.get("security")):
            return row.get("cashBalance") or row.get("cashUnblocked")
    return None


def trades(
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
    """Executed trades in the ``DD/MM/YYYY`` date window (stocks in/out).

    Optionally filter to one ``symbol`` (the app always sends one, e.g. the
    report screen's selected stock). Omit ``symbol`` to fetch everything.
    """
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
    return [Trade.from_dict(item) for item in raw]
