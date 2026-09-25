"""Buy orders."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import ORDER
from .base import OrderResult, OrderSession


def buy(
    client_code: str,
    nostr: str,
    symbol: str,
    volume: int,
    price: Optional[float] = None,
    order_type: str = ORDER["LIMIT"],
    market_type: str = ORDER["REGULAR"],
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
    extra: Optional[Dict[str, Any]] = None,
) -> OrderResult:
    """Place a buy order and wait for the broker confirmation.

    ``price=None`` with ``order_type=141`` is effectively a market buy
    (the app still sends a price; pass one explicitly to be safe).
    """
    session = OrderSession(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url, timeout=timeout,
    )
    try:
        return session.place(
            symbol=symbol, side=ORDER["BUY"], volume=volume, price=price,
            order_type=order_type, market_type=market_type, extra=extra,
        )
    finally:
        session.close()
