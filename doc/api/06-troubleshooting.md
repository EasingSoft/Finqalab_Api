# Troubleshooting

Failure modes in rough order of how often they bite.

---

## Installation

### `ModuleNotFoundError: No module named 'finqalab'`

Not installed, or installed in a different interpreter.

```bash
pip install -e .
python -c "import finqalab; print(finqalab.__version__)"
```

From a clone without installing, `PYTHONPATH=src` also works. In notebooks,
`%pip install -e .` rather than a bare `!pip install`.

### `ModuleNotFoundError: No module named 'Crypto'`

`pycryptodome` is missing — the import is `Crypto`, not `cryptography`.

```bash
pip install pycryptodome
```

### `ModuleNotFoundError: No module named 'websockets.sync'`

`websockets` is too old. The socket client uses the sync API, which needs 12+.

```bash
pip install -U websockets
```

Python 3.8 and below are unsupported regardless.

---

## Login

### `LoginRequired` on every login

The server answered **HTTP 207** — the device is not verified. This is the
normal first-run path, not a failure.

```python
try:
    client.login()
except LoginRequired:
    client.verify_device_otp(input("OTP: "))
    client.login()
```

If it recurs on a machine that worked before, the server no longer recognises
your `device_id`. Force a fresh one and verify again:

```python
client = FinqalabClient(user_id="00000", password="...", device_id="0123456789abcdef")
```

### The OTP is rejected

* **Case matters.** The code is mixed-case alphanumeric — `Ab3xY9`. Uppercase
  input fails.
* **It expired.** Codes are short-lived. Read the newest email and use the last
  code.
* **Wrong `user_id`.** The OTP body needs the same client code as the login.

### `FinqalabError: no password set`

`login()` was called on a client built without a password.

```python
FinqalabClient(user_id="00000", password="your-password")
# or
client.login(password="your-password")
```

### `LoginRequired` and HTTP 401 at the same time

They are unrelated. 401 is an expired JWT on *other* endpoints; 207 is login
challenging the device. Handle them separately.

---

## Tokens

### 401 on everything after a successful login

The cached token expired — 28-day lifetime.

```python
FinqalabClient(user_id="00000", password="...").login()
```

### The cached token looks wrong

`TokenStore` swallows every read error, so a corrupt or truncated file reads as
"no token" rather than raising. Delete it:

```python
FinqalabClient(user_id="00000").clear_token()
```

### A stale token shadows a fresh login

`MarketClient()` and friends load the file on construction. If you logged in
elsewhere, either construct them with the new token or re-`save_token()`:

```python
market = MarketClient(token=client.token, token_path=None)
```

### Sharing a token across several clients

They all read the same file, so one `login()` is enough. If a client seems not to
see it, check they are not pointed at a different `token_path` — or that
`token_path=None` is not suppressing the read.

---

## Market data

### `summaryV2` returns an empty list

Usually a bad token. The snapshot endpoints are authenticated. Call
`user_detail()` to confirm the token, then log in again if it 401s.

### `statistics()` or `graph()` return the wrong day

Two different date formats, both easy to get wrong:

| Call | Format |
|------|--------|
| `statistics(symbol, "14-06-2026")` | `DD-MM-YYYY` |
| `graph(symbol, date="2026-06-14")` | `YYYY-MM-DD` |

Passing the wrong one silently returns an empty or stale result rather than an
error.

### Weekend or holiday: empty candles, stale index

Normal. The exchange is closed and the API serves the last session. There is no
live REST tape — the socket.io feed is unavailable (see
[08-live-data-gap.md](../reverse/08-live-data-gap.md)).

### `percent_change` or `price` is a string

Genuine server behaviour — some numeric fields arrive as JSON strings. The typed
models convert what they can; read `.raw` for the original row.

### `index_news()` `lt` field will not parse

`lt` is a **JSON string inside a JSON response**. Parse it a second time:

```python
import json
tick = json.loads(row["lt"])
```

### `sector` prints as a number

It is a PSX sector code, not a label. `0824` is Oil & Gas.

### `summary()` is slow or huge

~430 KB, every symbol, no pagination. Cache it. Do not call it in a loop.

---

## Watchlists and alerts

### `create()` adds when I meant to remove

`status` is the switch, not a filter: `True` adds, `False` removes.

```python
wl.create("OGDC", watchlist=1, status=True)    # add
wl.create("OGDC", watchlist=1, status=False)   # remove
```

`watchlist` is a **string** `1`–`5`. Passing `0` or `6` is not rejected, it just
does nothing useful.

### `read()` returns empty lists

Watchlists start empty. A new account has nothing in any of the five. Also check
you are looking at the right key — the response is keyed `watchlist1`..
`watchlist5`, not `1`..`5`.

### Watchlist rows are enormous

Each row is a full snapshot plus a `livegraphs` intraday array. Normal, and the
reason `read()` is slow with several full lists.

### Alert creation returns a 4xx

Do not send a `title` — the server generates it. Send only `symbol`,
`notificationType`, `alertType`, `target`, `isDefault`, `isRecurring`. `target`
is a string, even for a whole number.

### `history()` shows things that are not price alerts

Corporate events (board meetings, dividends) come through the same feed. Check
`type`.

---

## WebSocket

### `StompError: timed out waiting for CONNECTED`

The socket opened but STOMP never completed. Usual causes:

* Wrong `client_code` or `nostr`.
* Market closed and the server drops the handshake.
* The `oms_user_id` / `session_token` path segments rotated — try passing
  explicit values.
* A proxy or middlebox on `wss://` that does not upgrade properly.

Raise `connect_timeout` from the default 15s on a slow connection.

### `StompError: connection closed`

The server closed mid-session. Reconnect. `recv()` raises this rather than
returning `None`, so a polling loop needs a try/except around it.

### `OrderListTimeout: no response for portfolio`

The wrapper converts every failure into this, so it covers timeouts, closed
sockets, and malformed frames alike.

Check the obvious first: **is the market open?** The server answers outside
trading hours with nothing, and an empty portfolio is the correct result. Only
suspect a bug during market hours.

### Empty order list during market hours

The order list is bounded by `fromDate`/`toDate`, which are `HH:MM` defaulting
to now. The server returns the window you asked for, so a narrow window is
empty if nothing traded in it. Widen the bounds explicitly to check.

### The connection dies after ~25 seconds

That is the SockJS heartbeat, not a failure. The client skips heartbeat frames
silently; you should never see them. If your own code is reading raw frames, skip
`h` and `o`.

### `websockets` version errors

`pip install -U websockets`. The sync client API needs 12+.

### Password rejected on the socket but REST login works

They are separate systems with separate checks. Confirm you are passing the
Finqalab account password as `nostr`, not a trading PIN. The PIN is a different
field in the profile and is not accepted here.

---

## Orders

### `OrderResult.success` is True but the order did not fill

`success` means the order was **accepted** (`VLD` validated, `ACK`
acknowledged). It does not mean executed. Poll for `FILLED`:

```python
o = order.place_and_wait("00000", "your-password", result.order_no)
print(o.order_status)
```

### `OrderResult.error == "TIMEOUT"`

No notification inside the window. **Ambiguous — the order may still have gone
through.** Check the order list before retrying, or you will double your
position.

### Rejected: "no investor account" / balance errors

Standard exchange and account-level rejections. They come back on
`order-service.notify` as a `status` with a `message`; read
`result.message` rather than the exception, since the call itself succeeded.

### Price rejected or order ignored

* `price` must be a **float**, not a string.
* Market orders: `order_type=ORDER["MARKET"]` (`141`) with `price=0.0`.
* `side` is capitalised — `Buy` / `Sell`, not `BUY` / `SELL`.
* Lot size: PSX instruments trade in defined lots. A volume that is not a valid
  lot size is rejected.

### `modify()` / `cancel()` behave strangely

⚠️ **Neither was captured on the wire.** Both are reconstructed from the OMS
payload plus the `neworder` shape. They are unproven. For a live account, cancel
in the app and place a fresh order.

---

## Payments

### Dates are off by decades in the cashbook

`createdAt` is epoch **milliseconds**, not seconds. `cashbook()` converts it
for you; if you read the raw rows, divide by 1000 before treating it as seconds.

### `withdrawal()` 4xx

Expected — the request shape was never captured. The V2 flow needs an OTP whose
body is also unknown. See
[`doc/reverse/05-known-gaps.md`](../reverse/05-known-gaps.md).

### `periodic_details()` ignores my date range

Server behaviour. It returns all history; the client filters locally on
`trade_date`. Wide windows mean downloading everything each time.

### PDF endpoints return garbage

They return PDF **bytes**, not JSON. Write them to a file:

```python
open("cashbook.pdf", "wb").write(payments.cashbook_pdf(body))
```

Request bodies are unconfirmed, so an empty or wrong body can produce a broken
document. Display-only, which is all the app does with them.

---

## Environment

### `FQ_APP_BUILD` has no effect

The server does not enforce the app build. `verify-version` returns 200 for any
value and login proceeds. Changing it changes nothing functional.

### Tokens and credentials in the wrong place

`FQ_USER_ID` / `FQ_PASSWORD` are used by the examples. The library itself takes
explicit arguments:

```python
FinqalabClient(user_id=..., password=...)
```

`StompClient.connect_from_env()` wants different names — `FQ_CLIENT_CODE` and
`FQ_NOSTR`. The library does not read the environment on its own; only the
example scripts do.

### Everything fails behind a proxy

`requests` honours `HTTPS_PROXY`; the `websockets` client may not, and SockJS
`wss://` upgrades are frequently broken by TLS-intercepting proxies. Test
outside the proxy before blaming the client.

---

## Still stuck

Collect these before asking:

1. The exact call and the exact exception, with traceback.
2. Whether the exchange was open.
3. `finqalab.__version__`, Python version, `requests` and `websockets` versions.
4. The response body for HTTP errors — `resp.text`, not just the status code.
5. Market data or `user_detail()` works, which isolates REST-vs-connection and
   auth-vs-payload.

Never include a JWT, password, OTP, client code, CNIC, mobile, or IBAN in a bug
report. Redact them.
