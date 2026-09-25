"""Unofficial Python client for the Finqalab / Next Capital API.

Covers the two transports the official app uses:

* **REST** (``staticapis.nextcapital.com.pk``) - auth, market data, watchlists,
  alerts, portfolio-adjacent info, deposits and withdrawals. Authenticated calls
  send the JWT from ``/v1/loginV3`` in an ``x-auth-token`` header.
* **STOMP over SockJS** (``trade.nextcapital.com.pk``) - the live trading
  channel: portfolio, order list, and order placement.

Quickstart::

    from finqalab import FinqalabClient, LoginRequired

    client = FinqalabClient(user_id="00000", password="your-password")
    try:
        client.login()
    except LoginRequired:
        client.verify_device_otp(input("email OTP: "))
        client.login()
    print(client.user_detail()["username"])

Package layout:

* ``client``     - REST auth (login V3, device OTP, token) and session misc
* ``stomp``      - trading WebSocket (STOMP 1.2 over SockJS)
* ``encryption`` - AES-256-CBC helpers for password / PIN / CNIC / mobile fields
* ``order``      - place / modify / cancel / list orders
* ``portfolio``  - holdings, cash balance, executed trades
* ``market``     - market summary, index snapshot, news, per-symbol detail
* ``watchlist``  - read / add / remove watchlist symbols
* ``alerts``     - alert permissions and delivered alert history
* ``payments``   - deposits, withdrawals, bank accounts, cashbook, reports
* ``oms``        - trade-intimation logging
* ``config``     - hosts, endpoints, and order/side constants
* ``models``     - typed wrappers over the raw JSON responses
* ``utils``      - device id, JWT decode, STOMP framing, token cache
"""

from .config import (
    API_HOST,
    APP_BUILD,
    LIVE_DATA_HOST,
    OMS_HOST,
    WS_HOST,
)
from .encryption import decrypt_base64, decrypt_field, decrypt_text, encrypt_password
from .client import FinqalabClient, FinqalabError, LoginRequired
from .stomp import StompClient, StompError
from .market import MarketClient
from .watchlist import WatchlistClient
from .alerts import AlertsClient
from .payments import PaymentsClient
from . import order
from . import portfolio
from . import oms

__version__ = "0.1.0"

__all__ = [
    "API_HOST",
    "APP_BUILD",
    "LIVE_DATA_HOST",
    "OMS_HOST",
    "WS_HOST",
    "decrypt_base64",
    "decrypt_field",
    "decrypt_text",
    "encrypt_password",
    "FinqalabClient",
    "FinqalabError",
    "LoginRequired",
    "StompClient",
    "StompError",
    "MarketClient",
    "WatchlistClient",
    "AlertsClient",
    "PaymentsClient",
    "order",
    "portfolio",
    "oms",
    "__version__",
]
