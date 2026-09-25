"""Lightweight typed wrappers around the raw JSON the API returns.

The wire formats come straight from the capture (``finqalab.db``); each
dataclass also accepts the raw dict so parsing failures can't break calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _as_dict(obj: Any) -> Dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


@dataclass
class OrderNotification:
    """Server confirmation pushed on ``/user/{client}/order-service.notify``."""

    order_no: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    price: Optional[str] = None
    quantity: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    action: Optional[str] = None
    time: Optional[str] = None
    trigger_price: Optional[Any] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderNotification":
        d = _as_dict(d)
        return cls(
            order_no=d.get("orderNo"),
            symbol=d.get("symbol"),
            side=d.get("side"),
            price=d.get("price"),
            quantity=d.get("quantity"),
            status=d.get("status"),
            message=d.get("message"),
            action=d.get("action"),
            time=d.get("time"),
            trigger_price=d.get("triggerPrice"),
        )

    @property
    def success(self) -> bool:
        return self.status in ("VLD", "ACKNOWLEDGED")


@dataclass
class Order:
    """One entry of the order list (``order-service/order-list``)."""

    order_number: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    volume: Optional[Any] = None
    price: Optional[Any] = None
    order_nature: Optional[str] = None
    order_special: Optional[str] = None
    order_status: Optional[str] = None
    market_type: Optional[str] = None
    order_date_time: Optional[str] = None
    valid_till: Optional[str] = None
    after_hour_order: Optional[Any] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Order":
        d = _as_dict(d)
        return cls(
            order_number=d.get("orderNumber"),
            symbol=d.get("symbol"),
            side=d.get("side"),
            volume=d.get("volume"),
            price=d.get("price"),
            order_nature=d.get("orderNature"),
            order_special=d.get("orderSpecial"),
            order_status=d.get("orderStatus"),
            market_type=d.get("marketType"),
            order_date_time=d.get("orderDateTime"),
            valid_till=d.get("valid_till"),
            after_hour_order=d.get("afterHourOrder"),
            raw=d,
        )


@dataclass
class Holding:
    """One row of the portfolio response (``order-service/portfolio``)."""

    security: Optional[str] = None
    quantity: Optional[Any] = None
    total_cost: Optional[str] = None
    cost_per_unit: Optional[str] = None
    current_price: Optional[str] = None
    current_value: Optional[str] = None
    cap_gain_loss: Optional[str] = None
    ret_of_inv: Optional[str] = None
    pf_weight: Optional[str] = None
    cash_unblocked: Optional[str] = None
    cash_blocked: Optional[str] = None
    cash_balance: Optional[str] = None
    grand_total: Optional[str] = None
    limit_withdrawal: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Holding":
        d = _as_dict(d)
        return cls(
            security=d.get("security"),
            quantity=d.get("quantity"),
            total_cost=d.get("totalCost"),
            cost_per_unit=d.get("costPerUnit"),
            current_price=d.get("currentPrice"),
            current_value=d.get("currentValue"),
            cap_gain_loss=d.get("capGainLoss"),
            ret_of_inv=d.get("retOfInv"),
            pf_weight=d.get("pfWeight"),
            cash_unblocked=d.get("cashUnblocked"),
            cash_blocked=d.get("cashBlocked"),
            cash_balance=d.get("cashBalance"),
            grand_total=d.get("grandTotal"),
            limit_withdrawal=d.get("limitWithdrawal"),
            raw=d,
        )


@dataclass
class Trade:
    """One executed trade (``periodicTradeDetailReportRequest``)."""

    symbol: Optional[str] = None
    trade_number: Optional[Any] = None
    trade_date: Optional[str] = None
    settlement_date: Optional[str] = None
    side: Optional[str] = None
    buy_qty: Optional[Any] = None
    sell_qty: Optional[Any] = None
    rate: Optional[Any] = None
    buy_amount: Optional[Any] = None
    sell_amount: Optional[Any] = None
    brok_amount: Optional[Any] = None
    cvt_amount: Optional[Any] = None
    wht_amount: Optional[Any] = None
    fed_amount: Optional[Any] = None
    net_amount: Optional[Any] = None
    order_number: Optional[str] = None
    order_nature: Optional[str] = None
    market_type: Optional[str] = None
    order_status: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Trade":
        d = _as_dict(d)
        return cls(
            symbol=d.get("symbol"),
            trade_number=d.get("trade_Number"),
            trade_date=d.get("trade_date"),
            settlement_date=d.get("settlement_date"),
            side=d.get("side"),
            buy_qty=d.get("buyQty"),
            sell_qty=d.get("sellQty"),
            rate=d.get("rate"),
            buy_amount=d.get("buyAmount"),
            sell_amount=d.get("sellAmount"),
            brok_amount=d.get("brokAmount"),
            cvt_amount=d.get("cvtAmount"),
            wht_amount=d.get("whtAmount"),
            fed_amount=d.get("fedAmount"),
            net_amount=d.get("netAmount"),
            order_number=d.get("orderNumber"),
            order_nature=d.get("orderNature"),
            market_type=d.get("marketType"),
            order_status=d.get("orderStatus"),
            raw=d,
        )


@dataclass
class Snapshot:
    """One symbol from ``/v1/marketSnapshot/summaryV2``."""

    symbol: Optional[str] = None
    name: Optional[str] = None
    sector: Optional[str] = None
    open: Optional[Any] = None
    high: Optional[Any] = None
    low: Optional[Any] = None
    price: Optional[Any] = None
    change: Optional[Any] = None
    percent_change: Optional[Any] = None
    volume: Optional[Any] = None
    bid: Optional[Any] = None
    ask: Optional[Any] = None
    listed_in: Optional[List] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Snapshot":
        d = _as_dict(d)
        return cls(
            symbol=d.get("Symbol"),
            name=d.get("name"),
            sector=d.get("sector"),
            open=d.get("Open"),
            high=d.get("High"),
            low=d.get("Low"),
            price=d.get("Price"),
            change=d.get("Change"),
            percent_change=d.get("PercentChange"),
            volume=d.get("Volume"),
            bid=d.get("Bid"),
            ask=d.get("Ask"),
            listed_in=d.get("listed_in"),
            raw=d,
        )


@dataclass
class NewsItem:
    id: Optional[Any] = None
    heading: Optional[str] = None
    excerpt: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    time: Optional[str] = None
    image: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NewsItem":
        d = _as_dict(d)
        return cls(
            id=d.get("id"),
            heading=d.get("heading"),
            excerpt=d.get("excerpt"),
            url=d.get("url"),
            source=d.get("source"),
            time=d.get("time"),
            image=d.get("image"),
            raw=d,
        )
