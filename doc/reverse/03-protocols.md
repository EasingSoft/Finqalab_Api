# Protocols

Wire formats. Four, of which two are implemented in the client.

| Protocol | Where |
|----------|-------|
| REST + JWT | `staticapis.nextcapital.com.pk` |
| AES-256-CBC | in and out of the profile |
| STOMP 1.2 over SockJS | `trade.nextcapital.com.pk` |
| socket.io 4 | `live-data.finqalab.com` — **unavailable** |

---

## 1. REST

### Transport

`https://staticapis.nextcapital.com.pk`, JSON, TLS. No certificate pinning was
observed to block the MITM CA once it was installed as a system cert.

### Headers

Authenticated requests send both, because the app does:

```
x-auth-token: <JWT>
cookie: xauth=<JWT>
content-type: application/json
accept: application/json
user-agent: Dart/3.12 (dart:io)
accept-encoding: gzip
```

The `user-agent` identifies Dart's `dart:io` rather than a browser. Matching it
is not required by the server, but it costs nothing.

`verify-version` is the exception — it is `application/x-www-form-urlencoded`.

### Auth flow

```
POST /v1/appVersion/verify-version        app_build=170        (form)
POST /v1/loginV3                          {...}                 -> 207 or 200
POST /v1/verifyDeviceVerificationOTP      {...}                 (only on 207)
```

Login body:

```json
{
  "id": "00000",
  "password": "<base64 AES-CBC ciphertext>",
  "device_token": "",
  "device_id": "0123456789abcdef",
  "os": "Android"
}
```

**HTTP 207** is the important detail. It is not an error code in the usual
sense — it means "device unknown, OTP emailed":

```
207  {"msg":"Unauthorized"}
```

The same credentials on a recognised device return 200 with the profile and a
`token`. A 207 mid-session is not a failure; it is a challenge.

`device_id` is 8 random bytes as hex, generated on the client and sent on every
login. The server remembers it per account. There is no device fingerprint —
no IMEI, no Android ID. Any 16-char hex string works, which is also why
supplying a new one forces a fresh OTP.

### OTP

Mixed-case alphanumeric — `Ab3xY9`. Not digits, and case-sensitive.

### Token

Standard JWT, 28-day expiry, `x-auth-token` header. Read the claims with
`finqalab.utils.decode_jwt`, but understand there is nothing to verify the
signature against: the client holds no key. It is a convenience for reading
`exp`, not a validation mechanism.

### Response envelope

`{"success": true, "data": ...}` for most endpoints. `summaryV2` uses
`message`. Every client method accepts `data` / `Data` variants, so a server
rename degrades rather than breaks.

### Inconsistencies

Some numerics arrive as JSON strings. `index_news`'s `lt` is a JSON string
nested inside the JSON. `sector` is a numeric code. Date formats vary per
endpoint — see [02-app-internals.md](02-app-internals.md).

---

## 2. AES-256-CBC

### What is encrypted

**Outbound** — the login password only.

**Inbound** — four profile fields:

| Field | Contents |
|-------|----------|
| `trading_pin_code` | Trading PIN |
| `mobileNo` | Mobile number |
| `cnic` | CNIC |
| `ibn_number` | IBAN |

### The scheme

```
AES-256-CBC, PKCS7 padding, base64 output
key: 32 bytes, hardcoded in the app
iv:  16 bytes, hardcoded, FIXED — not per-request
out: base64(AES-256-CBC-PKCS7(utf8(plaintext)))
```

```python
from finqalab import encrypt_password, decrypt_text

encrypt_password("your-password")   # -> base64 blob for loginV3
decrypt_text(profile["mobileNo"])   # -> "+92 3XX-XXXXXXX"
```

The `KEY` and `IV` constants are in `src/finqalab/encryption.py`.

### What this is not

Symmetric, static key, static IV, both public. It is not encryption in any
security sense:

* Anyone with this repository can decrypt any ciphertext the app produces, and
  encrypt anything the app would accept.
* A **fixed IV** means identical plaintexts produce identical ciphertexts. That
  leaks equality: two accounts with the same password, the same PIN, the same
  mobile number, are visibly identical in the ciphertext.
* The only thing protecting the password in transit is **TLS**.

Read [`SECURITY.md`](../../SECURITY.md) before building anything on this. Do not
reuse the construction for your own data.

### Not used on the WebSocket

The trading socket sends the password **in plaintext** in the STOMP `CONNECT`
frame. Different system, no AES. That is why the two auth systems are
documented separately in
[`doc/api/03-auth-and-tokens.md`](../api/03-auth-and-tokens.md).

---

## 3. STOMP 1.2 over SockJS

The trading protocol. The only one that carries portfolio and orders.

### Connection

```
wss://trade.nextcapital.com.pk/order-dispatch-websocket/{oms_user_id}/{session_token}/websocket
```

`oms_user_id` and `session_token` are shared constants baked into the app
(`291`, `4rjrnta5`), not per-user. Defaults in `config.py`, overridable.

### Three layers

```
SockJS framing            a["..."]  h  o  c[...]
  └─ STOMP 1.2 frames     COMMAND\nheader:value\n\nbody\x00
       └─ JSON payload
```

**SockJS.** Server frames are a one-character type tag followed by data:
`a` = array of messages, `h` = heartbeat (~25s), `o` = open, `c[...]` = close.
Heartbeats are noise and must be skipped.

**The client-to-server framing is the part that surprises people.** Every frame
is a JSON array containing one STOMP frame as a *string*:

```python
frame = "SEND\ndestination:...\n\n{...}\x00"
wire  = json.dumps([frame])     # '["SEND\\n...\\u0000"]'
```

`json.dumps` escapes the real newlines to `\n` and the NUL to `\u0000`. That is
what appears on the wire and what the capture shows. `finqalab.utils.wire()`
implements it.

**STOMP.** Standard 1.2: command line, `key:value` headers, blank line, body,
terminating NUL.

### Authentication

Sent in the first `CONNECT` frame, after the socket opens:

```
CONNECT
id:00000
nostr:your-password
accept-version:1.0,1.1,1.2
heart-beat:5000,5000

<NUL>
```

`id` = client code, `nostr` = **password in plaintext**. No AES here.

Response `CONNECTED`, or `ERROR` on bad credentials. The `accept-version` list
includes 1.0 and 1.1 but the server settles on 1.2.

### Topics

The asymmetric naming is the second surprise. **Dot before the client code in
requests, slash in replies:**

| Kind | Pattern |
|------|---------|
| Request | `/app/order-service/{topic}.{client_code}` |
| Reply | `/user/{client_code}/order-service/{topic}` |
| Order notify | `/user/{client_code}/order-service.notify` |

Observed topics: `portfolio`, `order-list`,
`periodicTradeDetailReportRequest`, and the bare `/app/order-service.{code}`
for order actions.

**Always SUBSCRIBE before you SEND.** The server can push the answer before your
`SEND` returns, and a late subscribe misses it permanently. `_subscribe_and_send`
in `order/order_list.py` gets the order right and is the right base for anything
new.

Some channels use an explicit subscription id — the app passes the client code
on `periodicTradeDetailReportRequest`. Both id and route must match the reply.

### Payloads

`portfolio` — bare JSON **array**, no envelope. Holdings plus a money row.

`order-list` — bare array. Request is bounded by `HH:MM` timestamps:

```json
{"pageSize":1,"fromIndex":0,"toIndex":50,
 "userAuthority":"TRADER","fromDate":"10:44","toDate":"10:44"}
```

`periodicTradeDetailReportRequest` — bare array of executed trades. The server
**ignores the date range** and returns all history; the client filters locally.

Order action — `actionType: "neworder"` to `/app/order-service.{code}`. The
confirmation arrives on `order-service.notify`, a different destination.

### Order body

```json
{
  "actionType":"neworder", "clientCode":"00000", "userId":"00000",
  "symbol":"OGDC", "side":"Buy", "volume":100, "price":118.0,
  "orderType":"140", "marketType":"REG",
  "discVolume":0, "orderProperty":111, "orignateSource":"W",
  "refno":"0", "subClientCode":"", "triggerPrice":0
}
```

`140` limit · `141` market · `142` stop · `143` stop-limit.
`REG` / `ODD` / `AH`. `Buy` / `Sell`, capitalised.

### Confirmation

```json
{"orderNo":"...","symbol":"OGDC","side":"Buy","price":"118.00",
 "quantity":"100","status":"VLD","message":"Order validated",
 "action":"neworder","time":"10:44:31","triggerPrice":0}
```

`VLD` = **validated, not filled.** `ACK` acknowledged, `FILLED` executed.
A successful call does not mean a fill.

### `modify` and `cancel`

**Not observed.** No such frame exists in the capture. Both are reconstructed
from the OMS trade-intimation payload plus the `neworder` shape, reusing
`actionType`. Unproven — treat any success as unverified.

---

## 4. socket.io 4 — unavailable

```
GET https://live-data.finqalab.com/socket.io/?EIO=4&transport=polling&...
```

Every attempt returned **503**. The handshake was visible; live frames never
were. Event names, payload shape, and authentication are all unknown, and no
substitute is implemented.

This is why there is no live tick in the client. `summaryV2` and `index_news`
are polled snapshots standing in for a tape. Investigation and next steps in
[08-live-data-gap.md](08-live-data-gap.md).

---

## 5. OMS

```
POST https://finqalab-oms-prod.finqalab.com/api/trade-intimation
```

No auth header observed. Fires after an order action so the OMS keeps a record
even if the notification is missed. The response echoes the payload; the schema
is inferred. **No effect on orders** — server-side audit convenience.

---

Next: [04-findings-and-decisions.md](04-findings-and-decisions.md)
