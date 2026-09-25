# What the API Can Do

Nine areas. Each section says what you can get, what the client exposes, and the
traps that will waste your time.

The API splits across two hosts:

| Host | Transport | Auth |
|------|-----------|------|
| `staticapis.nextcapital.com.pk` | REST over HTTPS | `x-auth-token` header (JWT) |
| `trade.nextcapital.com.pk` | WebSocket, STOMP over SockJS | client code + password in the `CONNECT` frame |
| `finqalab-oms-prod.finqalab.com` | REST | none observed |

Market data, watchlists, alerts, and payment history are all REST. Portfolio and
orders live on the WebSocket.

---

## 1. Authentication

See [03-auth-and-tokens.md](03-auth-and-tokens.md) for the full story.

| Call | Client | Notes |
|------|--------|-------|
| App version check | `FinqalabClient.verify_version()` | Not enforced by the server; failures are harmless |
| Log in | `.login()` | Returns the whole profile |
| Email device OTP | `.verify_device_otp(otp)` | Only on a new `device_id` |
| Profile | `.user_detail()` | `GET /v1/userDetailV2` |
| Session flags | `.portfolio_day_start()`, `.multiday_toggle()`, `.custom_popups()`, `.subscription_detail()` | Lightweight booleans the app reads on launch |

## 2. Market data

**No trading socket needed — a valid token is enough.**

| Call | Returns |
|------|---------|
| `market.snapshots()` | Every listed PSX symbol, ~870 rows, one request |
| `market.index_news()` | KSE100, KSE30, ALLSHR, KMIALLSHR levels |
| `market.statistics(symbol)` | Fundamentals: market cap, EPS, P/E, book value, dividend |
| `market.company(symbol)` | Description, registrar, board people, notices |
| `market.financial(symbol)` | Quarterly and annual statements |
| `market.graph(symbol, count, interval)` | Price/volume candles, daily or weekly |
| `market.news(page, news_type)` | Headlines; type 0-3 |

Traps:

* **`summary()` is not paginated.** It is ~430 KB every time. Cache it.
* **Date formats differ.** `statistics()` wants `DD-MM-YYYY`; `graph()` wants
  `YYYY-MM-DD`. Both default to today if you pass nothing.
* **`sector` is a numeric code**, not a label. `Sector: "0824"` is Oil & Gas.
* **Weekend and holiday gaps.** `graph()` and `statistics()` on a closed day
  return the previous session.
* **`index_news()` buries the live tick in a nested JSON string.** The `lt` field
  is itself JSON: `{"t":...,"x":...,"v":...}`.
* **Types are inconsistent.** Some numeric fields arrive as strings. The `.raw`
  attribute on every model keeps the untouched response.

## 3. Watchlists

| Call | Returns |
|------|---------|
| `watchlist.read(sort_by="custom")` | All five watchlists keyed `watchlist1`..`watchlist5` |
| `watchlist.create(symbol, watchlist, status)` | Add (`status=True`) or remove (`status=False`) |

Traps:

* **`read()` is a GET** with `?sortBy=custom`, not a POST with a body.
* **`watchlist` is passed as a string** (`"1"`, not `1`) and indexes 1-5.
* **`status` is the switch, not a filter.** `True` adds, `False` removes.
* **Rows are full snapshots.** Each symbol carries price, change, volume, bid,
  ask, lot size, and a `livegraphs` array of intraday points. It is a large
  payload.
* **Reordering a watchlist is not implemented.** The path is known but the
  request shape was never confirmed — see
  [`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).

## 4. Alerts

| Call | Returns |
|------|---------|
| `alerts.by_user_id(symbol=None)` | Alerts configured per symbol |
| `alerts.history()` | Alerts that have fired |
| `alerts.create(symbol, ...)` | Create or update a price alert |

Traps:

* **Do not send a `title`.** The server writes it. Send `symbol`,
  `notificationType`, `alertType`, `target`, `isRecurring`, `isDefault` and it
  answers with a generated title like `"Rises over 15"`.
* **`alertType` 2 is a percentage move** and `target` is the threshold, as a
  string.
* **Alerts fire on PSX corporate events too** — `history()` mixes price alerts
  with board-meeting and dividend notices, distinguishable by `type`.
* **Portfolio-wide alert settings are not implemented** (path known, shape
  unconfirmed).

## 5. Portfolio — WebSocket

| Call | Returns |
|------|---------|
| `portfolio.holdings(code, nostr)` | Typed `Holding` rows |
| `portfolio.cash_balance(code, nostr)` | Cash from the money row |
| `portfolio.portfolio(...)` | The raw rows, if you want them all |
| `portfolio.trades(code, nostr, from, to, symbol)` | Executed trades |

Traps:

* **The cash row is a holding.** It is the row whose `security` contains
  `"Money"`. Exclude it when summing stock value.
* **The response is a bare JSON array**, not an object. The client handles
  either.
* **`trades()` filters client-side.** The server ignores your date range and
  returns all history, so the client narrows it on `trade_date`. Dates go in as
  `DD/MM/YYYY` and come back as `YYYY-MM-DD`.
* **Each call opens its own socket.** The app batches portfolio and order-list
  on one connection; see `_subscribe_and_send` if you want to do the same.

## 6. Orders — WebSocket

| Call | Returns |
|------|---------|
| `order.order_list(code, nostr)` | Today's orders as typed `Order` rows |
| `order.buy(...)` / `order.sell(...)` | `OrderResult` with the confirmation |
| `order.OrderSession(...).place(...)` | Reuse one connection for several orders |
| `order.modify(...)` / `order.cancel(...)` | Change or kill a live order |
| `order.place_and_wait(...)` | Poll until your order number appears |
| `order.modify(...)` / `order.cancel(...)` | **Inferred, not captured** — see below |

Codes you need:

| Constant | Value | Meaning |
|----------|-------|---------|
| `ORDER["LIMIT"]` | `140` | Limit price |
| `ORDER["MARKET"]` | `141` | Market order |
| `ORDER["STOP"]` | `142` | Stop loss |
| `ORDER["STOP_LIMIT"]` | `143` | Stop limit |
| `ORDER["REGULAR"]` | `REG` | Regular board |
| `ORDER["ODD_LOT"]` | `ODD` | Odd lot |
| `ORDER["AFTER_HOURS"]` | `AH` | After hours |
| `ORDER["BUY"]` / `ORDER["SELL"]` | `Buy` / `Sell` | Side, capitalised |

Traps:

* **Status `VLD` means validated, not filled.** `ACK` is acknowledged,
  `FILLED` is done. Watch `order_status` rather than assuming success.
* **`price` must be a float.** Market orders send `0.0` with the type set to
  `141`.
* **The confirmation arrives on a different destination** than the request —
  `/user/{code}/order-service.notify` — and `OrderSession` subscribes before
  sending. Do not reorder those two steps.
* **There is no paper-trading mode.** Anything you place is real.
* **`modify()` and `cancel()` were never observed on the wire.** No modify or
  cancel frame appears in the capture. Both are reconstructed from the OMS
  trade-intimation payload plus the `neworder` shape, and they reuse the
  `actionType` field, which the capture does show changing. Treat them as
  unproven. The safe way to change or kill a live order is to cancel it in the
  app and place a new one.

## 7. Payments and funds

| Call | Returns |
|------|---------|
| `payments.deposits_history()` | Cash in |
| `payments.withdrawal_history()` | Cash out |
| `payments.cashbook()` | Both merged into a signed, date-sorted ledger |
| `payments.get_bank_codes()` | Bank name/code list |
| `payments.get_accounts()` | Registered beneficiary IBANs |
| `payments.periodic_details(code, nostr, from, to, symbol)` | Executed trades, stocks in and out |
| `payments.periodic_pdf(body)` / `.cashbook_pdf(body)` | The PDF bytes the app displays |

Traps:

* **`createdAt` is epoch milliseconds**, not seconds. `cashbook()` converts it
  to `YYYY-MM-DD` for you.
* **Withdrawals are negative** in the cashbook; deposits positive.
* **The PDF endpoints take an unconfirmed body shape.** They return bytes, not
  JSON. Treat them as display-only, which is all the app does with them.
* **Opening a new withdrawal is not implemented.** The V2 flow needs an OTP
  (`verifyOtpV2`) and that request was never captured. `withdrawal(body)` is
  there if you have already worked out the shape.

## 8. Live quotes — not available

`live-data.finqalab.com` runs socket.io for the live tape. The handshake
returned 503 on every attempt, so its event names, payload shape, and auth are
unknown. The REST `summaryV2` and `index_news` snapshots are the substitute —
they refresh on the app's polling cadence, not tick by tick. See
[`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).

## 9. OMS trade intimation

`finqalab.oms.trade_intimation(payload)` posts a record to
`finqalab-oms-prod.finqalab.com/api/trade-intimation`. The app fires it after an
order action so the OMS keeps a log even if the notification is missed. It is
informational — the response is a stored copy of what you sent. Useful for
audit trails.

---

## Not available in this client

Twenty-two endpoint paths are known but their request and response shapes were
never confirmed, so they are deliberately not implemented: withdrawal V2 and its
OTP, IBFT and PayFast deposits, account opening (AOF) and document upload,
subscription plans and activation, password change, account deactivation, live
socket.io quotes, and the search and discover feeds.

All of them are listed with their paths in
[`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).
