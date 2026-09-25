"""Order cancellation.

Like ``modify``, there is no captured ``cancel`` frame; this follows the
same ``/app/order-service.{client}`` SEND pattern with ``actionType:
cancel``. The server confirms via ``order-service.notify``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import ORDER
from .base import OrderResult, OrderSession


def cancel(
    client_code: str,
    nostr: str,
    order_no: str,
    symbol: str,
    volume: int,
    price: Optional[float] = None,
    side: str = ORDER["BUY"],
    market_type: str = ORDER["REGULAR"],
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
    extra: Optional[Dict[str, Any]] = None,
) -> OrderResult:
    body = {
        "actionType": "cancel",
        "clientCode": client_code,
        "userId": client_code,
        "orderNo": order_no,
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "price": float(price) if price is not None else 0.0,
        "orderType": ORDER["LIMIT"],
        "marketType": market_type,
        "discVolume": 0,
        "orderProperty": ORDER["NORMAL"],
        "orignateSource": "W",
        "refno": "0",
        "subClientCode": "",
        "triggerPrice": 0,
    }
    if extra:
        body.update(extra)
    session = OrderSession(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url, timeout=timeout,
    )
    try:
        return session._place(body)
    finally:
        session.close()
