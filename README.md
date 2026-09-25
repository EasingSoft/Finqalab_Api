# finqalab-api

Unofficial Python client for the **Finqalab** API — the backend behind the
Finqalab Android app, a PSX broker app for the Pakistan Stock Exchange
(broker: Next Capital, regulator: SECP).

Talk to the same REST endpoints and the same trading WebSocket the app uses,
from your own scripts. Market data, watchlists, alerts, portfolio, deposits,
withdrawals, and live order placement.

**Not affiliated with, endorsed by, or supported by Next Capital, Finqalab, or
U2 Ventures.** Use it only with an account you own. See
[SECURITY.md](SECURITY.md) before you publish anything built on it.

---

## Install

```bash
pip install git+https://github.com/EasingSoft/Finqalab_Api.git
```

From a clone:

```bash
pip install -e .
```

Requires Python 3.9+. Dependencies: `requests`, `pycryptodome`, `websockets`.

## Configure

```cmd
setx FQ_USER_ID "00000"
setx FQ_PASSWORD "your-password"
```

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `FQ_USER_ID` | yes | — | Client code / login `id` |
| `FQ_PASSWORD` | yes | — | Account password |
| `FQ_APP_BUILD` | no | `170` | App-build marker sent to the version check |

Never hardcode these in a file that gets committed.

## 60-second quickstart

```python
import os
from finqalab import FinqalabClient, LoginRequired, decrypt_text

user_id = os.environ.get("FQ_USER_ID")
password = os.environ.get("FQ_PASSWORD")
if not user_id or not password:
    raise SystemExit("Set FQ_USER_ID and FQ_PASSWORD first.")

client = FinqalabClient(user_id=user_id, password=password)

try:
    client.login()
except LoginRequired:
    # First login from a new machine: an OTP arrives by email.
    client.verify_device_otp(input("OTP from email: "))
    client.login()

profile = client.profile
print(profile["username"], profile["account_status"])
print("mobile:", decrypt_text(profile["mobileNo"]))   # arrives encrypted
print("multiday toggle:", client.multiday_toggle())
```

The JWT is cached at `~/.finqalab_token`, so the OTP step happens once per
machine. Clear it with `FinqalabClient(user_id="...").clear_token()`.

## What the API can do

| Area | What you get | Client |
|------|--------------|--------|
| Auth | login, email device OTP, profile, session flags | `FinqalabClient` |
| Market data | full PSX snapshot (~870 symbols), index levels, news, per-symbol statistics / company profile / financials / price graph | `MarketClient` |
| Watchlists | read 5 watchlists, add or remove a symbol | `WatchlistClient` |
| Alerts | alert permissions, delivered alert history, create price alerts | `AlertsClient` |
| Portfolio | holdings, cash balance, executed trades | `finqalab.portfolio` |
| Orders | place, modify, cancel, list, wait for confirmation | `finqalab.order` |
| Payments | deposit history, withdrawal history, bank codes, beneficiary accounts, cashbook ledger, periodic details, PDF reports | `PaymentsClient` |
| Live socket | STOMP over SockJS for portfolio and orders | `StompClient` |
| OMS | trade-intimation logging | `finqalab.oms` |

Full capability notes and the wire format for each call are in
**[doc/api/02-what-the-api-can-do.md](doc/api/02-what-the-api-can-do.md)**.

### Market data only — no trading socket needed

```python
from finqalab import MarketClient

market = MarketClient()               # picks up the saved token
for s in market.snapshots()[:5]:
    print(s.symbol, s.name, s.price, s.percent_change)
```

### Trading

```python
from finqalab import portfolio, order

code, nostr = "00000", "your-password"   # socket auth is code + password

for h in portfolio.holdings(code, nostr):
    print(h.security, h.quantity, h.current_value)

print(portfolio.cash_balance(code, nostr))

for o in order.order_list(code, nostr):
    print(o.order_number, o.side, o.symbol, o.volume, o.price, o.order_status)
```

Placing an order sends a real order to the exchange. Read
**[doc/api/05-trading-websocket.md](doc/api/05-trading-websocket.md)** before
you do it for the first time.

## Examples

| Script | Shows |
|--------|-------|
| [`examples/01_quickstart.py`](examples/01_quickstart.py) | login, the email-OTP branch, profile |
| [`examples/02_market_data.py`](examples/02_market_data.py) | indices, full market snapshot, one stock in depth, news |
| [`examples/03_portfolio_and_orders.py`](examples/03_portfolio_and_orders.py) | portfolio, order list, optional order placement |

Each has a matching transcript in
[`examples/expected_output/`](examples/expected_output/) showing exactly what a
real run prints.

## Documentation

**Using the API** — [`doc/api/`](doc/api/)

1. [Getting started](doc/api/01-getting-started.md)
2. [What the API can do](doc/api/02-what-the-api-can-do.md)
3. [Authentication and tokens](doc/api/03-auth-and-tokens.md)
4. [API reference](doc/api/04-api-reference.md)
5. [Trading WebSocket](doc/api/05-trading-websocket.md)
6. [Troubleshooting](doc/api/06-troubleshooting.md)

---

### Further reading

Methodology, application internals, and the complete record of endpoints —
including the ones this client does not expose — live in
**[`doc/reverse/`](doc/reverse/)**. Read it only if you need it.
