# Authentication and Tokens

Finqalab has **two independent authentication systems**. They share nothing —
not the credentials, not the token, not the transport. Confusing them is the most
common source of confusion with this API.

| | REST API | Trading WebSocket |
|---|---|---|
| Host | `staticapis.nextcapital.com.pk` | `trade.nextcapital.com.pk` |
| Transport | HTTPS | SockJS → WebSocket → STOMP |
| Credential | client code + **password**, then a JWT | client code + **password**, per connection |
| Identifier | `x-auth-token` header | `CONNECT` frame headers |
| Lifetime | 28 days | lifetime of the socket |

Once you have a JWT, every REST call is just that header. The WebSocket ignores
it entirely.

---

## 1. The REST login

### Step 1 — app version check (optional)

```
POST /v1/appVersion/verify-version
Content-Type: application/x-www-form-urlencoded

app_build=170
```

The app fires this before login to gate old builds. **The server does not
actually enforce it** — a wrong `app_build` still returns 200 and login proceeds
anyway. The client sends it for fidelity; you can skip it entirely.

Override with `FQ_APP_BUILD` if you want to match a different release.

### Step 2 — login

```
POST /v1/loginV3
Content-Type: application/json

{
  "id": "00000",
  "password": "<AES-CBC ciphertext, base64>",
  "device_token": "",
  "device_id": "0123456789abcdef",
  "os": "Android"
}
```

Two responses, and the difference is only in the status code:

**New device — HTTP 207**

```json
{"msg": "Unauthorized"}
```

`device_id` is unknown to the server, so it refuses and emails you a one-time
code. The body looks like an auth error but it is really a challenge. The client
raises `LoginRequired` on 207.

**Known device — HTTP 200**

The full profile comes back. This is every key the capture recorded (33 of
them), with the real values replaced:

```json
{
  "id": "00000",
  "token": "<JWT>",
  "timestamp": "2026-08-13T17:43:24.946Z",
  "trade": true,
  "submission_complete": true,
  "username": "<username>",
  "email": "<email>",
  "clientName": "<name>",
  "trading_pin_code": "<encrypted>",
  "mobileNo": "<encrypted>",
  "cnic": "<encrypted>",
  "ibn_number": "<encrypted>",
  "cnic_expiry": "<DD/MM/YYYY>",
  "hasPendingIBFTRequest": false,
  "hasPendingWithdrawalRequest": false,
  "instantDepositAcc": {"acct_no": "<number>", "iban_code": "<PK..>", "acct_desc": "..."},
  "cdcRastIban": {"iban": "<PK..>", "bank_name": "..."},
  "isRating": 0,
  "isFeedback": 0,
  "feedFormURL": "",
  "limit_percent_change": 10,
  "otp_is_verified": 1,
  "isBankTransfer": false,
  "isPayFast": false,
  "isRda": false,
  "tax_rate": 0.15,
  "commission_rate": 0.0025,
  "settlement_day": "You can withdraw settled funds only. ...",
  "account_status": "BASIC",
  "isPremiumStarted": false,
  "isPremiumEnded": false,
  "psx_media_url": "https://dps.psx.com.pk/download",
  "showSurvey": false
}
```

The whole payload is stored on `client.profile`. The `token` field is the JWT.

Worth knowing about these fields:

- `account_status` is an **account tier**, not a health flag. The captured
  value was `BASIC`. It is not `"Active"` and it does not gate trading.
- `trade` is the flag that actually matters — it gates order placement.
- `tax_rate` and `commission_rate` are **fractions**, not percentages
  (`0.15` = 15%). `commission_rate` was `0.0025`, i.e. 0.25%.
- `hasPendingIBFTRequest` and `hasPendingWithdrawalRequest` are the cheapest
  way to find out whether a withdrawal is still in flight.
- `settlement_day` is a human-readable sentence, not a date.

`isMultidayToggle` is **not** in this response. It is the sole field of
`GET /v1/multiday-toggle` — see `client.multiday_toggle()`.

### Step 3 — the email OTP (only on 207)

```
POST /v1/verifyDeviceVerificationOTP
Content-Type: application/json

{"user_id": "00000", "otp": "Ab3xY9", "device_id": "0123456789abcdef"}
```

```json
{"status": 1, "msg": "OTP verified successfully"}
```

Then `POST /v1/loginV3` again with the same body. This time it returns 200.

**The code is mixed-case alphanumeric** — `Ab3xY9`, not `123456`. Uppercase
input is rejected.

### device_id

```python
random_device_id()  # os.urandom(8).hex() -> 16 hex chars
```

Generated locally, reused on every subsequent request, and never sent anywhere
except in the login body and the OTP body. The server remembers it per account,
which is what makes the OTP a once-per-machine step.

It is not a device fingerprint in any meaningful sense — there is no IMEI, no
Android ID, no hardware. Any 16-character hex string will do. That is also why
generating a new one is a supported way to force a fresh OTP.

---

## 2. The password encryption

`password` in the login body is not plaintext. The app AES-encrypts it with a
**static 32-byte key and a static 16-byte IV** that ship in the app, then
base64-encodes the result.

```python
from finqalab.encryption import encrypt_password, decrypt_text

body = {"id": "00000", "password": encrypt_password("your-password"), ...}

decrypt_text(profile["mobileNo"])   # -> "+92 3XX-XXXXXXX"
```

Same scheme, same key, for `trading_pin_code`, `mobileNo`, `cnic`, and
`ibn_number` in the profile response.

The key and IV are in `src/finqalab/encryption.py` and are public. **This is not
encryption in any meaningful security sense** — it stops nothing, it only
reproduces what the server expects so the login is accepted. Read
[`SECURITY.md`](../../SECURITY.md) for why that matters and what it means for
anything you send through it.

---

## 3. The token

A standard JWT, three base64url segments. Send it as:

```
x-auth-token: <JWT>
```

The client also sets a matching `cookie: xauth=<JWT>`, because the app does both
and some endpoints prefer one over the other.

28-day lifetime. Read the claims without verifying anything:

```python
from finqalab.utils import decode_jwt, jwt_expires

decode_jwt(token)     # {"id": ..., "username": ..., "exp": 1767225600, ...}
jwt_expires(token)    # 1767225600
```

```python
import time
from finqalab.utils import jwt_expires

if jwt_expires(client.token) < time.time():
    client.login()   # refresh
```

`decode_jwt` does **not** check the signature. There is nothing to check it
against — the client has no key. It is a convenience for reading `exp`, nothing
more. Never treat it as proof a token is genuine.

### Where it is stored

`~/.finqalab_token`, JSON, created on first successful login:

```json
{"token": "<JWT>", "user_id": "00000"}
```

`TokenStore` swallows every read error — a missing file, an unreadable file, a
truncated file all read as "no token" rather than raising. A corrupt token file
therefore looks like a logged-out client, not like a crash.

```python
FinqalabClient(user_id="00000").clear_token()   # delete it
```

Opt out entirely with `token_path=None`, or point it somewhere else:

```python
FinqalabClient(user_id="00000", token_path="/run/secrets/finqalab")
```

### Sharing one token

Every REST client reads the same file, so this works:

```python
from finqalab import FinqalabClient, MarketClient, WatchlistClient, AlertsClient, PaymentsClient

FinqalabClient(user_id="00000", password="...").login()   # or reuse the cache

market = MarketClient()
wl = WatchlistClient()
alerts = AlertsClient()
payments = PaymentsClient()
```

You can also hand a JWT to any of them directly, which is the cleanest option for
short-lived tools:

```python
market = MarketClient(token="<JWT>", token_path=None)   # nothing touches disk
```

---

## 4. The WebSocket login

Completely separate. No JWT, no device id, no OTP — just your credentials again,
sent in the STOMP `CONNECT` frame after the SockJS handshake:

```
CONNECT
id:00000
nostr:your-password
accept-version:1.0,1.1,1.2
heart-beat:5000,5000

<NUL>
```

The server answers `CONNECTED` and the connection is authenticated. `nostr` is
literally your Finqalab password in plaintext. Every subsequent frame on that
socket is scoped to that client code.

Two extra path segments are also needed in the handshake URL — an OMS user id
and a session token. They ship as defaults in `config.py` and have proved stable;
override them if the server ever rotates them. See
[05-trading-websocket.md](05-trading-websocket.md).

**Because the password crosses the wire in plaintext on every connection, do not
run this client against a live account on an untrusted network.** TLS is the only
protection, exactly as for the REST side.

---

## 5. What expires when

| Credential | Expires | Symptom | Fix |
|-----------|---------|---------|-----|
| JWT | 28 days | 401 on any REST call | `client.login()` |
| Verified `device_id` | server-side, effectively forever | HTTP 207 on login | `verify_device_otp()` again |
| WebSocket | on disconnect | `ConnectionClosed` | reconnect |
| Trading session | PSX market hours | empty order list | reconnect during market hours |

A 401 is the normal expiry signal. A 207 on login is the normal "new machine"
signal. Neither is a bug.

---

Next: [API reference](04-api-reference.md) · [Trading WebSocket](05-trading-websocket.md)
