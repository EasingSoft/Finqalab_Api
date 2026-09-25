"""Fetch the order list over the trading WebSocket.

Mirrors the capture::

    SEND /app/order-service/order-list.<client_code>
    body: {"pageSize":1,"fromIndex":0,"toIndex":50,
           "userAuthority":"TRADER","fromDate":"10:44","toDate":"10:44"}
    -> MESSAGE on /user/<client_code>/order-service.order-list
       [ {order row}, ... ]            # the body is a bare JSON array
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..models import Order
from ..stomp import StompClient
from ..utils import now_pkst_hhmm

logger = logging.getLogger("finqalab.order")


class OrderListTimeout(Exception):
    pass


def _subscribe_and_send(
    client: StompClient,
    client_code: str,
    topic: str,
    body: Dict[str, Any],
    timeout: float = 8.0,
) -> Any:
    import time

    dest = f"/app/order-service/{topic}.{client_code}"
    sub = client.subscribe(topic)
    client.send(dest, body)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            headers, data = client.recv(timeout=deadline - time.time())
        except TimeoutError:
            break
        if data is None:
            continue
        return data
    raise OrderListTimeout(f"no response for {topic}")


def order_list(
    client_code: str,
    nostr: str,
    page_size: int = 1,
    from_index: int = 0,
    to_index: int = 50,
    user_authority: str = "TRADER",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 8.0,
) -> List[Order]:
    """Return the current order list.

    Body mirrors the capture; ``from_date`` / ``to_date`` are ``HH:MM``
    bounds (default to now, which is what the app sends).
    """
    if from_date is None:
        from_date = now_pkst_hhmm()
    if to_date is None:
        to_date = now_pkst_hhmm()
    body = {
        "pageSize": page_size,
        "fromIndex": from_index,
        "toIndex": to_index,
        "userAuthority": user_authority,
        "fromDate": from_date,
        "toDate": to_date,
    }
    client = StompClient(
        client_code, nostr, oms_user_id=oms_user_id,
        session_token=session_token, url=url,
    )
    try:
        with client:
            data = _subscribe_and_send(client, client_code, "order-list", body, timeout)
        if isinstance(data, list):
            raw_list = data
        else:
            raw_list = (data or {}).get("OrderList") or (data or {}).get("Data") or []
        return [Order.from_dict(item) for item in raw_list]
    except Exception as exc:
        raise OrderListTimeout(str(exc))


def place_and_wait(
    client_code: str,
    nostr: str,
    order_no: str,
    oms_user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    url: Optional[str] = None,
    timeout: float = 15.0,
) -> Optional[Order]:
    """Block until ``order_no`` appears in the order list (used after placing).

    Returns the matching order, or the last order list seen if the deadline
    passes first.
    """
    import time

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        orders = order_list(
            client_code, nostr,
            oms_user_id=oms_user_id, session_token=session_token,
            url=url, timeout=min(8.0, deadline - time.time()),
        )
        for o in orders:
            if o.order_number == order_no:
                return o
        last = orders
        time.sleep(1.0)
    return last
