# Trading WebSocket

Portfolio, orders, and executed trades all live on a second connection —
`wss://trade.nextcapital.com.pk` — running **STOMP 1.2 over SockJS**. The JWT
from REST is irrelevant here; this socket authenticates with your client code
and password directly.

Read this before you place an order. There is no paper-trading mode.

---

## Connection

```
wss://trade.nextcapital.com.pk/order-dispatch-websocket/{oms_user_id}/{session_token}/websocket
```

Two path segments beyond the client code are needed. They ship as defaults:

```python
WS_SESSION_OMS_USER_ID = "291"   # config.py
WS_SESSION_TOKEN      = "4rjrnta5"
```

These are fixed app-side identifiers, not per-user credentials, and have proved
stable. Override if the server ever rotates them:

```python
StompClient(code, nostr, oms_user_id="291", session_token="4rjrnta5")
```

`StompClient` is a context manager that opens the socket and completes the
handshake:

```python
from finqalab import StompClient

with StompClient("00000", "your-password") as ws:
    print("connected")
```

`websockets` must be new enough for `websockets.sync.client` — Python 3.9+ and
`websockets >= 12`.

## Authentication

Immediately after the socket opens, a STOMP `CONNECT` frame goes out:

```
CONNECT
id:00000
nostr:your-password
accept-version:1.0,1.1,1.2
heart-beat:5000,5000

<NUL>
```

`id` is your client code, `nostr` is your Finqalab password **in plaintext**. No
AES on this path. The server answers:

```
CONNECTED
version:1.2
session:...

<NUL>
```

A failed `CONNECT` comes back as an `ERROR` frame and raises `StompError`. If
nothing arrives before `connect_timeout` (default 15s), you get
`StompError("timed out waiting for CONNECTED")`.

**Because the password crosses the wire in plaintext on every connection, do not
use this client on an untrusted network.**

## Framing

SockJS, not raw WebSocket. Every client frame is a JSON array holding one STOMP
frame as a **string**:

```python
frame  = "SEND\ndestination:...\n\n{...}\x00"
wire   = json.dumps([frame])            # "[\"SEND\\n...\\u0000\"]"
```

Real newlines and the trailing NUL inside the string get escaped to `\n` and
`\u0000` by `json.dumps`. That is exactly what the capture shows, and
`finqalab.utils.wire()` does it for you.

Server → client:

| Frame | Meaning |
|-------|---------|
| `a["..."]` | a STOMP `MESSAGE` — the useful one |
| `h` | SockJS heartbeat, roughly every 25s — ignore it |
| `o` | SockJS open marker |
| `c[...]` | SockJS close — the connection is gone |

`parse_frame()` strips the `a` prefix, parses the array, strips the NUL, and
splits headers from body. Heartbeats return `(None, None)` and the read loop
skips them, so you never see one.

## Topics

Three-way naming. This is the part that trips people up:

| Kind | Pattern | Example |
|------|---------|---------|
| Request | `/app/order-service/{topic}.{client_code}` | `/app/order-service/portfolio.00000` |
| Reply | `/user/{client_code}/order-service/{topic}` | `/user/00000/order-service/portfolio` |
| Order notify | `/user/{client_code}/order-service.notify` | — |

Note the **dot before the client code in the request and the slash in the reply.**
They are not symmetric.

Always `SUBSCRIBE` to the reply before you `SEND` the request. The server can
push the answer before your `SEND` call returns, and a late subscribe misses it.
`_subscribe_and_send()` in `order/order_list.py` does it in the right order and
is the right starting point for anything new.

```python
ws.subscribe("portfolio")                                   # /user/{code}/order-service/portfolio
ws.send("/app/order-service/portfolio.00000", body)        # explicit destination
ws.send_action("order-list", body)                          # /app/order-service/order-list.{code}
```

Some channels use an explicit subscription id (the app passes the client code on
`periodicTradeDetailReportRequest`). Both the id and the route must match what
the reply expects:

```python
ws.subscribe_raw("/user/00000/order-service.periodicTradeDetailReportRequest",
                 subscription_id="00000")
```

## Reading

```python
headers, data = ws.recv(timeout=8.0)
```

Returns `(headers, parsed_json_body)` of the next `MESSAGE`. Body parsing is
lenient — JSON if it parses, raw text if not. Raises `TimeoutError` on the
deadline, `StompError` if the connection closes or the server sends `ERROR`.

## Timeouts

The default is 8 seconds. Reasons to raise it:

* Order placement during a busy open.
* `place_and_wait` polling, which reconnects each round.
* A slow mobile network — the handshake alone can take a few seconds.

`_subscribe_and_send` converts anything that goes wrong into
`OrderListTimeout(f"no response for {topic}")`, which is what the
`portfolio` and `order` modules raise. An empty result and a timeout look
similar from the outside, so treat `OrderListTimeout` as "probably outside
market hours" before assuming a bug.

## Portfolio

```python
from finqalab import portfolio

for h in portfolio.holdings("00000", "your-password"):
    print(h.security, h.quantity, h.cost_per_unit, h.current_value)

print("cash:", portfolio.cash_balance("00000", "your-password"))
```

Response is a **bare JSON array**, not an envelope. `Holding` fields: `security`,
`quantity`, `totalCost`, `costPerUnit`, `currentPrice`, `currentValue`,
`capGainLoss`, `retOfInv`, `pfWeight`, `cashUnblocked`, `cashBlocked`,
`cashBalance`, `grandTotal`, `limitWithdrawal`.

**Cash arrives as a holding**, usually a row whose `security` contains `"Money"`.
Exclude it when summing stock value. `cash_balance()` finds it for you.

Each call opens and closes its own socket. The app batches portfolio and order
list on one connection; reuse `_subscribe_and_send` if you want the same.

## Executed trades

```python
for t in portfolio.trades("00000", "your-password", "01/06/2026", "30/06/2026", symbol="FCEPL"):
    print(t.trade_date, t.side, t.symbol, t.buy_qty, t.sell_qty, t.rate, t.net_amount)
```

Dates go out as `DD/MM/YYYY`; `trade_date` comes back `YYYY-MM-DD`.

**The server ignores your date range and returns all history** — the client
filters locally on `trade_date`. If you call this for a wide window you are
downloading your entire trade history every time. Fetch once, filter yourself,
cache.

`payments.periodic_details()` is the same request through the payments client.

## Order list

```python
from finqalab import order

for o in order.order_list("00000", "your-password"):
    print(o.order_number, o.side, o.symbol, o.volume, o.price, o.order_status)
```

`fromDate` / `toDate` are `HH:MM`, defaulting to now — the app sends the current
time, and so does the client, which is why the list is "today's orders".

## Placing an order

⚠️ **This sends a real order to the exchange.**

```python
from finqalab import order, ORDER

result = order.buy("00000", "your-password", symbol="OGDC", volume=100, price=118.0)
print(result)
print(result.success, result.order_no, result.status, result.message)
```

```python
order.sell("00000", "your-password", symbol="OGDC", volume=100, price=118.0)
```

`price` must be a float. For a market order use `order_type=ORDER["MARKET"]`
(`141`) and `price=0.0`.

### One connection for several orders

`OrderSession` is the efficient path — handshake once, then send as many orders
as you like:

```python
with order.OrderSession("00000", "your-password") as session:
    r1 = session.place("OGDC", ORDER["BUY"], 100, 118.0)
    r2 = session.place("HBL",  ORDER["SELL"], 50, 210.5)
```

`place(symbol, side, volume, price, order_type, market_type)`.

### Order body

```json
{
  "actionType": "neworder", "clientCode": "00000", "userId": "00000",
  "symbol": "OGDC", "side": "Buy", "volume": 100, "price": 118.0,
  "orderType": "140", "marketType": "REG",
  "discVolume": 0, "orderProperty": 111, "orignateSource": "W",
  "refno": "0", "subClientCode": "", "triggerPrice": 0
}
```

| Field | Values |
|-------|--------|
| `orderType` | `140` limit · `141` market · `142` stop · `143` stop-limit |
| `marketType` | `REG` regular · `ODD` odd lot · `AH` after hours |
| `side` | `Buy` · `Sell` — capitalised |
| `orderProperty` | `111` (normal) |
| `orignateSource` | `W` |

### Confirmation

The reply is **not** on the request destination. `OrderSession` subscribes to
`/user/{client}/order-service.notify`, sends, then waits:

```json
{"orderNo":"<order-no>","symbol":"OGDC","side":"Buy","price":"118.00",
 "quantity":"100","status":"VLD","message":"Order validated",
 "action":"neworder","time":"10:44:31","triggerPrice":0}
```

| Status | Meaning |
|--------|---------|
| `VLD` | **validated — not filled** |
| `ACK` / `ACKNOWLEDGED` | acknowledged by the OMS |
| `FILLED` | executed |

`OrderResult.success` is `True` for `VLD` and `ACKNOWLEDGED`. **That means the
order was accepted, not that you got your price.** Poll
`order.place_and_wait()` or the order list to watch `order_status` change to
`FILLED`.

`OrderResult` never raises for a rejected order — it returns
`success=False` with `error` set. `TIMEOUT` means no notification arrived within
the window, which is ambiguous: the order may still have gone through. **Check
the order list before retrying, or you will double your position.**

### Modify and cancel

```python
order.modify("00000", "your-password", order_no="...", symbol="OGDC", volume=100, price=119.0)
order.cancel("00000", "your-password", order_no="...", symbol="OGDC", volume=100)
```

⚠️ **Neither was captured on the wire.** Both are reconstructed from the OMS
trade-intimation payload plus the `neworder` shape, reusing `actionType`.
Unproven. For a live account, cancel in the app and place a new order.

## OMS intimation

After an order action the app posts a copy to
`finqalab-oms-prod.finqalab.com/api/trade-intimation` so the OMS has a log even
if the notification is missed. `oms.trade_intimation(payload)`. No auth header
observed; the schema is inferred. It has no effect on your order — it is a
server-side audit convenience.

## Practical notes

* **Market hours.** The server answers outside trading hours, but returns an
  empty list. An empty order list outside market hours is normal.
* **One socket per call by default.** `portfolio`, `order_list`, and
  `trades` each open their own. For repeated polling, keep a session open.
* **Heartbeats are ~25s** and the client advertises `heart-beat:5000,5000`. Long
  idle periods are fine; do not add your own keepalive.
* **`websockets` sync API.** Blocking, single-threaded, one socket at a time.
  For concurrent trading, run each session in its own thread.
* **Password in plaintext.** `nostr` is your account password. It is not stored
  anywhere in this repo, but it does cross the network on every connection.

Next: [Troubleshooting](06-troubleshooting.md)
