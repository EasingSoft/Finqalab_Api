# API Reference

Every implemented endpoint, with its real request and response shape.

Base URL: `https://staticapis.nextcapital.com.pk`, except the trading socket
(`wss://trade.nextcapital.com.pk`) and the OMS logger.

**Contents**

1. [Conventions](#conventions)
2. [REST — auth](#rest--auth)
3. [REST — market data](#rest--market-data)
4. [REST — watchlists](#rest--watchlists)
5. [REST — alerts](#rest--alerts)
6. [REST — payments](#rest--payments)
7. [WebSocket — portfolio, trades, orders](#websocket--portfolio-trades-orders)
8. [OMS](#oms)
9. [Summary table](#summary-table)

---

## Conventions

**Headers.** Authenticated REST calls send both, because the app does:

```
x-auth-token: <JWT>
cookie: xauth=<JWT>
content-type: application/json
accept: application/json
user-agent: Dart/3.12 (dart:io)
```

**Response envelope.** Most endpoints return `{"success": true, "data": ...}`.
`summaryV2` is the exception — its list is under `message`, not `data`. Every
client method unwraps this for you and also accepts `Data` / `data` variants, so
a server-side key rename degrades rather than breaks.

**Types are not consistent.** Some numerics arrive as JSON strings, some as
numbers. Typed models convert to Python types; `.raw` always holds the
untouched row if you need the original.

**Dates.**

| Context | Format |
|---------|--------|
| `statistics()` query | `DD-MM-YYYY` |
| `graph()` query | `YYYY-MM-DD` |
| STOMP `fromDate` / `toDate` | `DD/MM/YYYY` |
| STOMP `trade_date` response | `YYYY-MM-DD` |
| Order-list `fromDate` / `toDate` | `HH:MM` |
| `createdAt` in payments | epoch **milliseconds** |
| Profile `cnic_expiry` | `DD/MM/YYYY` |

**Error handling.** `raise_for_status()` on every REST call, so HTTP failures
raise `requests.HTTPError`. WebSocket calls return `OrderResult(success=False)`
or raise `StompError` / `OrderListTimeout` rather than raising on STOMP-level
errors.

---

## REST — auth

Base: `staticapis.nextcapital.com.pk`. Client: `FinqalabClient`.

### `POST /v1/appVersion/verify-version`

Form-encoded, not JSON.

```
app_build=170
```

Not enforced by the server. `verify_version(app_build=170)`.

### `POST /v1/loginV3`

```json
{
  "id": "00000",
  "password": "<base64 AES-CBC>",
  "device_token": "",
  "device_id": "0123456789abcdef",
  "os": "Android"
}
```

| Status | Body | Meaning |
|--------|------|---------|
| `207` | `{"msg":"Unauthorized"}` | New device, OTP emailed — raises `LoginRequired` |
| `200` | full profile + `token` | Logged in; `client.profile` is populated |

Profile fields: `id`, `username`, `email`, `account_status`, `cnic_status`,
`cnic_expiry`, `tax_charged`, `commission_charged`, `isMultidayToggle`, and the
encrypted `trading_pin_code`, `mobileNo`, `cnic`, `ibn_number`.

### `POST /v1/verifyDeviceVerificationOTP`

```json
{"user_id": "00000", "otp": "Ab3xY9", "device_id": "0123456789abcdef"}
```

```json
{"status": 1, "msg": "OTP verified successfully"}
```

Mixed-case alphanumeric. No auth header needed — the `user_id` in the body is
the identity. `verify_device_otp(otp)`.

### `GET /v1/userDetailV2`

Profile refresh. `user_detail()`.

### Session flags

| Endpoint | Returns | Method |
|----------|---------|--------|
| `GET /v1/portfolio-day-start` | `{"data": {...}}` | `portfolio_day_start()` |
| `GET /v1/multiday-toggle` | `{"data":{"isMultidayToggle":true}}` | `multiday_toggle()` → `bool` |
| `GET /v1/custom_popups` | `{"data": [...]}` | `custom_popups()` |
| `GET /v1/subscription/subscription-detail` | plan state | `subscription_detail()` |

---

## REST — market data

Client: `MarketClient`. All GET, all token-authenticated.

### `GET /v1/marketSnapshot/summaryV2`

Every listed PSX symbol, ~870 rows, in one response. **No pagination params.**
~430 KB — cache it.

```json
{"message": [
  {"Symbol":"OGDC","name":"Oil & Gas Development Corporation",
   "sector":"0824","Open":"118.00","High":"119.50","Low":"117.00",
   "Price":"118.00","Change":"1.50","PercentChange":"1.29",
   "Volume":"2841200","Bid":"118.00","Ask":"118.50","listed_in":["N"]}
]}
```

`summary()` → raw dict. `snapshots()` → `list[Snapshot]`:

```python
for s in market.snapshots():
    print(s.symbol, s.name, s.price, s.percent_change, s.volume, s.bid, s.ask)
```

`sector` is a numeric PSX sector code, not a label. Several fields arrive as
strings.

### `GET /v1/snapshot/index_news`

```json
{"data": {"index": [
  {"symbol":"KSE100","name":"KSE 100 Index","close":"28150.00",
   "percent_change":"0.42","turnover":"...",
   "lt":"{\"t\":...,...}","ltp":"28150.00","ltpc":"0.42"}
]}}
```

`lt` is the live tick, itself a JSON **string** — parse it separately. `index_news()`
returns the raw dict.

### `GET /v1/snapshot/detail/statistics`

Query: `symbol`, `date` (**`DD-MM-YYYY`**, defaults to today).

Fundamentals and price bands: `{"data": {"statistics": {...}}}`. `statistics(symbol, date=None)`.

### `GET /v1/snapshot/detail/company`

Query: `symbol`. Profile: description, board, registrar, notices, people. `company(symbol)`.

### `GET /v1/snapshot/detail/financial`

Query: `symbol`. `{"data": {"annually": {"periods": [...]}, "quarterly": {...}}}`. `financial(symbol)`.

### `GET /v1/snapshot/detail/graph`

Query: `symbol`, `count`, `type` (`d` daily / `w` weekly), `date` (**`YYYY-MM-DD`**,
defaults to today). Price/volume candles. `graph(symbol, count=1, interval="d", date=None)`.

Weekend and holiday requests return the previous session.

### `GET /v1/news`

Query: `page` (0-based), `type` (0-3). `{"data": [{"id","heading","excerpt","url","source","time","image"}]}`.
`news(page=0, news_type=0)` → `list[NewsItem]`.

---

## REST — watchlists

Client: `WatchlistClient`.

### `GET /v1/watchlist/read?sortBy=custom`

All five lists in one call.

```json
{"success": true, "data": {
  "watchlist1": [ { "Symbol":"HBL", "Price":"...", "livegraphs":[...] } ],
  "watchlist2": [], "watchlist3": [], "watchlist4": [], "watchlist5": []
}}
```

`read(sort_by="custom")` → dict keyed `watchlist1`..`watchlist5`. Each row is a
full snapshot including a `livegraphs` intraday array — the payload is large.

### `POST /v1/watchlist/create`

```json
{"symbol": "OGDC", "watchlist": "1", "status": true}
```

```json
{"success": true, "data": "Watchlist updated"}
```

`create(symbol, watchlist=1, status=False)`. `status` is the switch:
`True` adds, `False` removes. `watchlist` is a string, 1-5.

Reordering is not implemented — the path is known, the request shape is not.

---

## REST — alerts

Client: `AlertsClient`.

### `GET /v1/alert_permission/byUserId`

Optional `symbol` query. `{"data": [{"symbol":"MZNPETF","defaultEvents":[],"customEvents":[]}]}`.
`by_user_id(symbol=None)`.

### `GET /v1/alert_permission/history`

```json
{"data": [
  {"user_id":"00000","symbol":"OGDC","title":"Rises over 15","type":2,
   "target":"15","alertType":2,"date":"2026-06-14","timestamp":1750000000000,
   "data":{...}}
]}
```

`history()`. Mixes price alerts with corporate-event notices (board meetings,
dividends) — `type` distinguishes them.

### `POST /v1/alert_permission`

```json
{
  "symbol": "OGDC",
  "notificationType": 0,
  "alertType": 2,
  "target": "15",
  "isDefault": false,
  "isRecurring": true
}
```

The server **generates the title** and echoes it back. Do not send one.
`create(symbol, notification_type=0, alert_type=2, target="15", is_recurring=True, is_default=False)`.

`alertType` 2 is a percentage move; `target` is the threshold as a string.

Portfolio-wide alert settings are not implemented.

---

## REST — payments

Client: `PaymentsClient`. `deposits_history`, `withdrawal_history`,
`get_bank_codes`, `get_accounts` are GET; the rest POST.

### `GET /v1/deposit_amount/usersDepositHistoryV2`

```json
{"data": [{"id":"...","amount":50000,"createdAt":1750000000000,
           "status":"...","payment_method":"...","payment_status":"..."}]}
```

`createdAt` is epoch **milliseconds**.

### `GET /v1/withdrawal`

Same row shape, negative-direction amounts. Also the POST target for a new
withdrawal — but see the caveat below.

### `GET /v1/withdrawal/getBankCodeList`

`[{"name":"...","code":"..."}]`.

### `GET /v1/withdrawal/getAllAccounts`

Registered beneficiary IBANs.

### `POST /v1/withdrawal`

**Request shape never captured.** `withdrawal(body)` is a raw passthrough. The
V2 flow needs an OTP (`verifyOtpV2`) whose body is also unknown. Do not guess
here — see [`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).

### `GET /v1/generatePeriodicDetailsPDF`, `GET /v1/generateCashBookPDF`

Return **PDF bytes**, not JSON. `periodic_pdf(body)` / `cashbook_pdf(body)` return
`bytes`. Request bodies unconfirmed; display-only, which is all the app does.

### Composed: `cashbook()`

`cashbook()` merges deposits (positive) and withdrawals (negative) into one
date-sorted ledger:

```python
[{"date": "2026-06-14", "type": "DEPOSIT", "amount": 50000,
  "method": "IBFT", "status": "SUCCESS"}, ...]
```

### Composed: `periodic_details()`

Executed trades over the **WebSocket** (not REST):

```python
payments.periodic_details("00000", "your-password", "01/06/2026", "30/06/2026")
```

`fromDate` / `toDate` go as `DD/MM/YYYY`. **The server ignores them and returns
all history**, so the client filters on `trade_date` (`YYYY-MM-DD`) locally.

---

## WebSocket — portfolio, trades, orders

Client: `StompClient`, plus the `portfolio` and `order` modules. Full protocol
in [05-trading-websocket.md](05-trading-websocket.md).

### `order-service/portfolio`

Request:

```json
{"clientCode": "", "sequenceId": "1750000000000"}
```

Response is a **bare JSON array**, not an envelope:

```json
[{"security":"OGDC","quantity":100,"totalCost":"11800.00","costPerUnit":"118.00",
  "currentPrice":"118.00","currentValue":"11800.00","capGainLoss":"0.00",
  "retOfInv":"0.00","pfWeight":"...","cashUnblocked":"...","cashBlocked":"..."},
 {"security":"Money Market Fund","cashBalance":"50000.00",
  "cashUnblocked":"50000.00","grandTotal":"61800.00","limitWithdrawal":"..."}]
```

| Call | Returns |
|------|---------|
| `portfolio(client_code, nostr)` | raw rows |
| `portfolio.holdings(client_code, nostr)` | `list[Holding]` |
| `portfolio.cash_balance(client_code, nostr)` | cash scalar |

**Cash is a holding.** Exclude the money row when summing stock value.
`cash_balance` finds it by `cashBalance` key or a `Money` substring in `security`.

### `order-service/order-list`

Request:

```json
{"pageSize": 1, "fromIndex": 0, "toIndex": 50,
 "userAuthority": "TRADER", "fromDate": "10:44", "toDate": "10:44"}
```

`fromDate` / `toDate` are `HH:MM`, defaulting to now.

Response is a bare array of order rows:

```json
[{"orderNumber":"<order-no>","symbol":"OGDC","side":"Buy","volume":100,
  "price":"118.00","orderNature":"REG","orderSpecial":"NORMAL",
  "orderStatus":"FILLED","marketType":"REG",
  "orderDateTime":"2026-06-14T10:44:31.000+05:00","valid_till":"...",
  "afterHourOrder":false}]
```

`order_list(client_code, nostr, page_size=1, from_index=0, to_index=50, user_authority="TRADER", from_date=None, to_date=None)`
→ `list[Order]`.

`place_and_wait(client_code, nostr, order_no, timeout=15.0)` polls until the
order number appears.

### `order-service/periodicTradeDetailReportRequest`

```json
{"clientCode":"00000","fromDate":"01/06/2026","toDate":"30/06/2026","symbol":"FCEPL"}
```

Bare array of executed trades:

```json
[{"symbol":"FCEPL","trade_Number":"...","trade_date":"2026-06-14",
  "settlement_date":"2026-06-16","side":"Buy","buyQty":100,"sellQty":0,
  "rate":"118.00","buyAmount":"11800.00","sellAmount":"0","brokAmount":"...",
  "cvtAmount":"...","whtAmount":"...","fedAmount":"...","netAmount":"...",
  "orderNumber":"...","orderNature":"REG","orderStatus":"FILLED"}]
```

`portfolio.trades(...)` or `payments.periodic_details(...)`. Both filter by date
client-side.

### `order-service` (new order)

Sent to `/app/order-service.{client_code}`:

```json
{
  "actionType": "neworder",
  "clientCode": "00000",
  "userId": "00000",
  "symbol": "OGDC",
  "side": "Buy",
  "volume": 100,
  "price": 118.0,
  "orderType": "140",
  "marketType": "REG",
  "discVolume": 0,
  "orderProperty": 111,
  "orignateSource": "W",
  "refno": "0",
  "subClientCode": "",
  "triggerPrice": 0
}
```

The confirmation arrives **after** a subscribe to
`/user/{client}/order-service.notify`:

```json
{"orderNo":"<order-no>","symbol":"OGDC","side":"Buy","price":"118.00",
 "quantity":"100","status":"VLD","message":"Order validated",
 "action":"neworder","time":"10:44:31","triggerPrice":0}
```

`subscribe_raw` **before** `send` — the server can push before you are listening.
`OrderSession` does this for you. `OrderResult.success` is `True` for `VLD` and
`ACKNOWLEDGED`.

| Call | Result |
|------|--------|
| `order.buy(client_code, nostr, symbol, volume, price, order_type, market_type)` | `OrderResult` |
| `order.sell(...)` | `OrderResult` |
| `order.OrderSession(client_code, nostr).place(symbol, side, volume, price, ...)` | `OrderResult`, reusable connection |
| `order.modify(...)` | **Inferred, not captured** |
| `order.cancel(...)` | **Inferred, not captured** |

Order type codes: `140` limit, `141` market, `142` stop, `143` stop-limit.
Market: `REG`, `ODD`, `AH`. Side: `Buy`, `Sell` — capitalised.

`VLD` means **validated, not filled.** `ACK` acknowledged, `FILLED` done.

---

## OMS

### `POST https://finqalab-oms-prod.finqalab.com/api/trade-intimation`

No auth header observed. The app fires it after an order action so the OMS
keeps a log even if the notification is missed.

`oms.trade_intimation(payload)` posts a dict and returns the echoed body (or
text — the endpoint returns nothing meaningful). Schema inferred from capture.
Informational only; it has no effect on your orders.

---

## Summary table

| Method | Path | Client call | Auth |
|--------|------|-------------|------|
| POST | `/v1/appVersion/verify-version` | `verify_version` | none |
| POST | `/v1/loginV3` | `login` | none |
| POST | `/v1/verifyDeviceVerificationOTP` | `verify_device_otp` | none |
| GET | `/v1/userDetailV2` | `user_detail` | JWT |
| GET | `/v1/portfolio-day-start` | `portfolio_day_start` | JWT |
| GET | `/v1/multiday-toggle` | `multiday_toggle` | JWT |
| GET | `/v1/custom_popups` | `custom_popups` | JWT |
| GET | `/v1/subscription/subscription-detail` | `subscription_detail` | JWT |
| GET | `/v1/marketSnapshot/summaryV2` | `summary`, `snapshots` | JWT |
| GET | `/v1/snapshot/index_news` | `index_news` | JWT |
| GET | `/v1/snapshot/detail/statistics` | `statistics` | JWT |
| GET | `/v1/snapshot/detail/company` | `company` | JWT |
| GET | `/v1/snapshot/detail/financial` | `financial` | JWT |
| GET | `/v1/snapshot/detail/graph` | `graph` | JWT |
| GET | `/v1/news` | `news` | JWT |
| GET | `/v1/watchlist/read?sortBy=custom` | `WatchlistClient.read` | JWT |
| POST | `/v1/watchlist/create` | `WatchlistClient.create` | JWT |
| GET | `/v1/alert_permission/byUserId` | `AlertsClient.by_user_id` | JWT |
| GET | `/v1/alert_permission/history` | `AlertsClient.history` | JWT |
| POST | `/v1/alert_permission` | `AlertsClient.create` | JWT |
| GET | `/v1/deposit_amount/usersDepositHistoryV2` | `deposits_history` | JWT |
| GET | `/v1/withdrawal` | `withdrawal_history` | JWT |
| POST | `/v1/withdrawal` | `withdrawal` (unconfirmed body) | JWT |
| GET | `/v1/withdrawal/getBankCodeList` | `get_bank_codes` | JWT |
| GET | `/v1/withdrawal/getAllAccounts` | `get_accounts` | JWT |
| POST | `/v1/generatePeriodicDetailsPDF` | `periodic_pdf` (bytes) | JWT |
| POST | `/v1/generateCashBookPDF` | `cashbook_pdf` (bytes) | JWT |
| WS | `/app/order-service/portfolio.{code}` | `portfolio` | code+password |
| WS | `/app/order-service/order-list.{code}` | `order_list` | code+password |
| WS | `/app/order-service/periodicTradeDetailReportRequest.{code}` | `trades`, `periodic_details` | code+password |
| WS | `/app/order-service.{code}` | `buy`, `sell`, `modify`, `cancel` | code+password |
| POST | `oms/api/trade-intimation` | `trade_intimation` | none |

Known paths that are **not** implemented: see
[`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).

Next: [Trading WebSocket](05-trading-websocket.md) · [Troubleshooting](06-troubleshooting.md)
