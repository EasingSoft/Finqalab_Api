"""Shared order-flow plumbing: the STOMP session wrapper and result type."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..config import NEWORDER_DEFAULTS, ORDER
from ..models import OrderNotification
from ..stomp import StompClient

logger = logging.getLogger("finqalab.order")


@dataclass
class OrderResult:
    """Outcome of an order call."""

    success: bool
    notification: Optional[OrderNotification] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

    @property
    def order_no(self) -> Optional[str]:
        return self.notification.order_no if self.notification else None

    def __str__(self) -> str:
        if self.error:
            return f"Order failed: {self.error}"
        if self.notification:
            return (
                f"{self.notification.side} {self.notification.quantity} "
                f"{self.notification.symbol} @ {self.notification.price} "
                f"[{self.notification.status}] #{self.notification.order_no} "
                f"- {self.notification.message}"
            )
        return f"Order {self.status}/{self.message}"


class OrderSession:
    """One connection + handshake + order, mirroring ``process_order`` in
    ``order bot/orderbot.py``."""

    def __init__(
        self,
        client_code: str,
        nostr: str,
        oms_user_id: Optional[str] = None,
        session_token: Optional[str] = None,
        url: Optional[str] = None,
        timeout: float = 8.0,
    ):
        self.client_code = client_code
        self.nostr = nostr
        self.timeout = timeout
        self._stomp = StompClient(
            client_code, nostr, oms_user_id=oms_user_id,
            session_token=session_token, url=url,
        )

    def place(
        self,
        symbol: str,
        side: str,
        volume: int,
        price: Optional[float] = None,
        order_type: str = "140",
        market_type: str = "REG",
        extra: Optional[Dict[str, Any]] = None,
    ) -> OrderResult:
        body = build_neworder(
            client_code=self.client_code,
            symbol=symbol,
            side=side,
            volume=volume,
            price=price,
            order_type=order_type,
            market_type=market_type,
            extra=extra,
        )
        return self._place(body)

    def _place(self, body: Dict[str, Any]) -> OrderResult:
        from ..stomp import StompError

        try:
            with self._stomp:
                self._stomp.send(f"/app/order-service.{self.client_code}", body)
                sub = self._stomp.subscribe_raw(
                    f"/user/{self.client_code}/order-service.notify"
                )
                import time

                deadline = time.time() + self.timeout
                while time.time() < deadline:
                    try:
                        headers, data = self._stomp.recv(timeout=deadline - time.time())
                    except TimeoutError:
                        return OrderResult(success=False, error="TIMEOUT")
                    note = OrderNotification.from_dict(data)
                    logger.info("order notify: %s", note)
                    return OrderResult(
                        success=note.success,
                        notification=note,
                        status=note.status,
                        message=note.message,
                    )
                return OrderResult(success=False, error="TIMEOUT")
        except StompError as exc:
            return OrderResult(success=False, error=str(exc))
        except Exception as exc:
            return OrderResult(success=False, error=f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        self._stomp.close()


def build_neworder(
    client_code: str,
    symbol: str,
    side: str,
    volume: int,
    price: Optional[float] = None,
    order_type: str = ORDER["LIMIT"],
    market_type: str = ORDER["REGULAR"],
    trigger_price: Any = 0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the ``neworder`` SEND body (captured shape)."""
    body = {
        **NEWORDER_DEFAULTS,
        "clientCode": client_code,
        "userId": client_code,
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "price": float(price) if price is not None else 0.0,
        "orderType": order_type,
        "marketType": market_type,
        "triggerPrice": trigger_price,
    }
    if extra:
        body.update(extra)
    return body
