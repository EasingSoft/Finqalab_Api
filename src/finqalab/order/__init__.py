"""Order placement over the trading WebSocket.

``buy.py`` / ``sell.py`` wrap the STOMP ``neworder`` flow used by the app:

1. ``SEND /app/order-service.{client_code}`` with the order body
2. ``SUBSCRIBE /user/{client}/order-service.notify`` (id: sub-N)
3. wait for the ``MESSAGE`` confirmation (``status: VLD`` / ``ACKNOWLEDGED``)

Order body (captured)::

    {"actionType":"neworder","clientCode":"<client_code>","discVolume":0,
     "orderProperty":111,"orderType":"140","orignateSource":"W",
     "price":137.0,"refno":"0","side":"Sell","subClientCode":"",
     "symbol":"FCEPL","triggerPrice":0,"userId":"<client_code>","volume":1,
     "marketType":"REG"}
"""

from .base import OrderSession, OrderResult
from .buy import buy
from .sell import sell
from .modify import modify
from .cancel import cancel
from .order_list import order_list, place_and_wait

__all__ = [
    "OrderSession",
    "OrderResult",
    "buy",
    "sell",
    "modify",
    "cancel",
    "order_list",
    "place_and_wait",
]
