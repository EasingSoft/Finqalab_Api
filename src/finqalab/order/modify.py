"""Order modification.

The capture has no ``modify`` frame; this is inferred from the OMS
trade-intimation payload (``orderNo``, ``symbol``, ``side``, ``volume``,
``price``) plus the ``neworder`` shape. The server acknowledges on
``order-service.notify`` like any order action.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import ORDER
from .base import OrderResult, OrderSession


def modify(
    client_code: str,
    nostr: str,
    order_no: str,
    symbol: str,
    volume: int,
    price: Optional[float] = None,
    side: str = ORDER["BUY"],
    order_type: str = ORDER["LIMIT"],
    market_type: str = ORDER["REGULAR"],
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
    extra: Optional[Dict[str, Any]] = None,
) -> OrderResult:
    body = {
        "actionType": "modify",
        "clientCode": client_code,
        "userId": client_code,
        "orderNo": order_no,
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "price": float(price) if price is not None else 0.0,
        "orderType": order_type,
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
