# Getting Started

## 1. Install

```bash
pip install git+https://github.com/EasingSoft/Finqalab_Api.git
```

Or from a clone:

```bash
git clone https://github.com/EasingSoft/Finqalab_Api.git
cd Finqalab_Api
pip install -e .
```

Python 3.9 or newer. The package pulls in `requests`, `pycryptodome` and
`websockets`.

## 2. Set your credentials

Never put these in a committed file. Environment variables are the simplest
safe option.

```bash
# Linux / macOS
export FQ_USER_ID=00000
export FQ_PASSWORD='your-password'
```

```powershell
# Windows PowerShell
$env:FQ_USER_ID = "00000"
$env:FQ_PASSWORD = "your-password"
```

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `FQ_USER_ID` | yes | — | Your client code, the `id` you type when logging in to the app |
| `FQ_PASSWORD` | yes | — | Your account password |
| `FQ_APP_BUILD` | no | `170` | App-build marker for the version check |

For anything longer-lived, a `.env` file plus a loader works. `.env` is already
in `.gitignore` — see [`.env.example`](../../.env.example).

## 3. Log in

```python
from finqalab import FinqalabClient, LoginRequired

client = FinqalabClient(user_id="00000", password="your-password")

try:
    client.login()
except LoginRequired:
    client.verify_device_otp(input("OTP from your email: "))
    client.login()

print(client.profile["username"])
```

`client.profile` is the full login response: client code, username, email,
account status, tax and commission rates, and the encrypted `trading_pin_code`,
`mobileNo`, `cnic` and `ibn_number`.

### The OTP step

The first time you log in from a machine, the server does not know that
`device_id`, so it answers **HTTP 207** instead of a token and emails you a
one-time code:

```
POST /v1/loginV3        ->  207  {"msg":"Unauthorized"}
POST /v1/verifyDeviceVerificationOTP
     {"user_id":"00000","otp":"Ab3xY9","device_id":"..."}
     -> 200 {"status":1,"msg":"OTP verified successfully"}
POST /v1/loginV3        ->  200  {... "token":"<JWT>" ...}
```

The code is mixed-case alphanumeric. Once the `device_id` is verified the server
remembers it, so this only happens once per machine.

`device_id` is 8 random bytes rendered as hex, generated locally on first use and
reused afterwards. If you want a fresh OTP, construct the client with your own:

```python
client = FinqalabClient(user_id="00000", password="...", device_id="0123456789abcdef")
```

## 4. The token is cached

After a successful login the JWT is written to `~/.finqalab_token`. Later runs
pick it up automatically, so you can skip the OTP:

```python
from finqalab import MarketClient

market = MarketClient()      # no arguments - reads the cached token
```

Useful operations:

```python
FinqalabClient(user_id="00000").clear_token()   # delete the cached token
FinqalabClient(user_id="00000").user_detail()   # check the token is still valid
```

The token is a standard JWT with a 28-day lifetime. When it expires you get a
401 and simply log in again.

If you would rather not use the cache at all, pass `token_path=None` or hand a
JWT straight to any client:

```python
market = MarketClient(token="<JWT>", token_path=None)
```

## 5. Make your first call

```python
from finqalab import MarketClient

market = MarketClient()

# Index levels
for row in market.index_news()["data"]["index"]:
    print(row["symbol"], row["close"], row["percent_change"])

# The whole market in one request
snapshots = market.snapshots()
print(len(snapshots), "symbols")
for s in snapshots[:5]:
    print(f"{s.symbol:<8} {s.name:<32} {s.price:>10} {s.percent_change:>8}")

# One instrument
print(market.statistics("OGDC")["data"]["statistics"])
print(market.company("OGDC")["data"]["description"][:200])
print(market.financial("OGDC")["data"]["annually"]["periods"])
print(market.graph("OGDC", count=10, interval="d")["data"][-3:])

# Headlines
for item in market.news(page=0, news_type=0)[:5]:
    print(item.source, "-", item.heading)
```

## 6. Watchlists and alerts

```python
from finqalab import WatchlistClient, AlertsClient

wl = WatchlistClient()
lists = wl.read()                       # {"watchlist1": [...], ...}
print(len(lists.get("watchlist1", [])), "symbols in watchlist 1")

wl.create("OGDC", watchlist=1, status=True)    # add
wl.create("OGDC", watchlist=1, status=False)   # remove

alerts = AlertsClient()
print(alerts.by_user_id("OGDC"))        # alerts set on one symbol
print(alerts.history()[:3])             # recently delivered alerts
alerts.create("OGDC", alert_type=2, target="15")   # "rises over 15%"
```

## 7. Portfolio and orders

These use a second, separate connection. The trading socket authenticates with
your client code and your password directly, so `nostr` is just your
`FQ_PASSWORD`.

```python
from finqalab import portfolio, order

code, nostr = "00000", "your-password"

for h in portfolio.holdings(code, nostr):
    print(h.security, h.quantity, h.cost_per_unit, h.current_value)

print("cash:", portfolio.cash_balance(code, nostr))

for o in order.order_list(code, nostr):
    print(o.order_number, o.side, o.symbol, o.volume, o.order_status)
```

Before you place anything, read
[05-trading-websocket.md](05-trading-websocket.md). There is no paper-trading
mode.

## Next

* [What the API can do](02-what-the-api-can-do.md) — every area, in detail
* [Authentication and tokens](03-auth-and-tokens.md) — both auth systems explained
* [API reference](04-api-reference.md) — endpoint tables with real payloads
* [Troubleshooting](06-troubleshooting.md) — when a call fails
