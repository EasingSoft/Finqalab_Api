"""Hosts, endpoints, and protocol constants.

Hosts
-----
``staticapis.nextcapital.com.pk``   main REST API (``x-auth-token`` JWT)
``trade.nextcapital.com.pk``        trading WebSocket (STOMP over SockJS)
``finqalab-oms-prod.finqalab.com``  OMS trade-intimation logging
``live-data.finqalab.com``          market-data socket.io feed

Override the app-build marker with the ``FQ_APP_BUILD`` environment variable.
The server does not currently enforce it, so the default is fine.
"""

import os

API_HOST = "staticapis.nextcapital.com.pk"
WS_HOST = "trade.nextcapital.com.pk"
OMS_HOST = "finqalab-oms-prod.finqalab.com"
LIVE_DATA_HOST = "live-data.finqalab.com"

API_SCHEME = "https"
API_BASE = f"{API_SCHEME}://{API_HOST}"
WS_SCHEME = "wss"
OMS_SCHEME = "https"
OMS_BASE = f"{OMS_SCHEME}://{OMS_HOST}"

APP_BUILD = int(os.environ.get("FQ_APP_BUILD", "170"))

USER_AGENT = "Dart/3.12 (dart:io)"
ACCEPT = "application/json"
CONTENT_TYPE = "application/json"

API = {
    "verify_version": "/v1/appVersion/verify-version",
    "login_v3": "/v1/loginV3",
    "verify_device_otp": "/v1/verifyDeviceVerificationOTP",
    "user_detail": "/v1/userDetailV2",
    "portfolio_day_start": "/v1/portfolio-day-start",
    "multiday_toggle": "/v1/multiday-toggle",
    "custom_popups": "/v1/custom_popups",
    "subscription_detail": "/v1/subscription/subscription-detail",
}

MARKET = {
    "summary_v2": "/v1/marketSnapshot/summaryV2",
    "index_news": "/v1/snapshot/index_news",
    "statistics": "/v1/snapshot/detail/statistics",
    "company": "/v1/snapshot/detail/company",
    "graph": "/v1/snapshot/detail/graph",
    "financial": "/v1/snapshot/detail/financial",
    "news": "/v1/news",
}

WATCHLIST = {
    "read": "/v1/watchlist/read",
    "create": "/v1/watchlist/create",
}

ALERTS = {
    "by_user_id": "/v1/alert_permission/byUserId",
    "history": "/v1/alert_permission/history",
    "create": "/v1/alert_permission",
}

PAYMENTS = {
    "deposits_history": "/v1/deposit_amount/usersDepositHistoryV2",
    "withdrawal": "/v1/withdrawal",
    "bank_code_list": "/v1/withdrawal/getBankCodeList",
    "accounts": "/v1/withdrawal/getAllAccounts",
    "periodic_pdf": "/v1/generatePeriodicDetailsPDF",
    "cashbook_pdf": "/v1/generateCashBookPDF",
}

# Endpoints whose paths are known but which have not been exercised against the
# live API. They are intentionally NOT exposed by the client; see
# doc/reverse/05-known-gaps.md for the full inventory.

OMS = {
    "trade_intimation": "/api/trade-intimation",
}

WS_STOMP_ENDPOINT = "/order-dispatch-websocket/{oms_user_id}/{session_token}/websocket"

# Path segments observed in a working handshake URL. Their generation is not
# documented publicly and they have proved stable in the field, so they ship as
# defaults. Override via the oms_user_id / session_token arguments of
# StompClient if the server ever rotates them.
WS_SESSION_OMS_USER_ID = "291"
WS_SESSION_TOKEN = "4rjrnta5"

ORDER = {
    "LIMIT": "140",
    "MARKET": "141",
    "STOP": "142",
    "STOP_LIMIT": "143",
    "REGULAR": "REG",
    "ODD_LOT": "ODD",
    "AFTER_HOURS": "AH",
    "BUY": "Buy",
    "SELL": "Sell",
    "NORMAL": 111,
}

NEWORDER_DEFAULTS = {
    "actionType": "neworder",
    "discVolume": 0,
    "orderProperty": ORDER["NORMAL"],
    "orderType": ORDER["LIMIT"],
    "orignateSource": "W",
    "refno": "0",
    "subClientCode": "",
    "triggerPrice": 0,
    "marketType": ORDER["REGULAR"],
}
