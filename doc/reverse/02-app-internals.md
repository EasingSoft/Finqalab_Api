# Application Internals

What the app is, how it is built, and what each piece of it talks to.

---

## The app

| Property | Value |
|----------|-------|
| Package | `com.mobile.finqalab` |
| Version | 4.0.2 (`versionCode` 170) |
| Framework | **Flutter** (Dart) |
| Android UID | 10044 |
| Publisher | U2 Ventures |
| Broker | Next Capital |
| Regulator | SECP (Pakistan) |
| Minimum observed | Android 7.0 / SDK 25 |

Flutter matters for two reasons, both covered elsewhere:

* `dart:io` ignores the Android system proxy, which is what made traffic capture
  hard ([01-capture-approach.md](01-capture-approach.md)).
* The AOT-compiled Dart snapshot is the only place the endpoints appear in
  source form. Dart string constants survive into `libapp.so` and are readable
  with `strings`, and Blutter is the tool for a deeper look at the AOT snapshot
  and its pool objects. The endpoint paths in this repository were recovered
  from exactly that — `strings` on the extracted `libapp.so` plus the confirmed
  traffic capture. **Blutter** (or reFlutter, or Doldrums for the pool) is the
  right tool if you want the full symbol map; jadx covers the Java/Android
  wrapper.

## Hosts

| Host | Purpose |
|------|---------|
| `staticapis.nextcapital.com.pk` | **Main REST API.** Everything except trading |
| `trade.nextcapital.com.pk` | **Trading WebSocket.** STOMP over SockJS |
| `finqalab-oms-prod.finqalab.com` | OMS trade-intimation logging |
| `live-data.finqalab.com` | socket.io live market tape — **unavailable**, see [08](08-live-data-gap.md) |
| `cms-prod.finqalab.com` | Content management / announcements |
| `finbot.finqalab.com` | FinBot assistant |
| `aof-mobile.nextcapital.com.pk` | Account opening form (AOF) |
| `analytics.capitalstake.com` | Analytics |

Two are infrastructure for the client: `staticapis` and `trade`. The rest are
feature-specific and mostly out of scope.

## Dart structure

Dart filenames, recovered from the AOT snapshot. They are the map of the app's
own architecture.

| File | Responsibility |
|------|----------------|
| `helpers/api_manager.dart` | REST layer — base URL, headers, `x-auth-token` |
| `helpers/auth_controller.dart` | Login, device OTP, token storage |
| `helpers/stomp_config.dart` | SockJS + STOMP configuration for the trading socket |
| `models/` | Response models |
| `screens/` | UI, one directory per feature |
| `services/` | Feature services wrapping `api_manager` |

The Python client mirrors this split closely — `client.py` is `api_manager` +
`auth_controller`, `stomp.py` is `stomp_config`, and each `*.py` module is one
feature service.

## Features and their endpoints

Mapping each app screen to what it calls. "Not implemented" entries are in
[05-known-gaps.md](05-known-gaps.md).

### Auth and session

`POST /v1/appVersion/verify-version` → `POST /v1/loginV3` →
`POST /v1/verifyDeviceVerificationOTP` on 207 → `GET /v1/userDetailV2`.

Then on launch: `GET /v1/portfolio-day-start`, `/v1/multiday-toggle`,
`/v1/custom_popups`, `/v1/subscription/subscription-detail`.

### Home and market

`GET /v1/marketSnapshot/summaryV2` for the full market, `/v1/snapshot/index_news`
for indices, `/v1/news` for the feed.

### Stock detail

`GET /v1/snapshot/detail/{statistics,company,financial,graph}`. The graph is the
price chart; `interval` is `d` or `w`.

### Watchlist

`GET /v1/watchlist/read?sortBy=custom` and `POST /v1/watchlist/create`. Five
lists. Reordering exists in the UI; its request shape was never captured.

### Alerts

`GET /v1/alert_permission/{byUserId,history}` and `POST /v1/alert_permission`.
The app's alert screen mixes price alerts with corporate events.

### Portfolio

`SEND /app/order-service/portfolio.{code}` on the trading socket. Returns
holdings plus a money row.

### Orders

`SEND /app/order-service.order-list.{code}` to list, and
`SEND /app/order-service.{code}` with `actionType: "neworder"` to place. The
confirmation arrives on `/user/{code}/order-service.notify`.

After any order action: `POST` to the OMS trade-intimation endpoint.

### Payments

`GET /v1/deposit_amount/usersDepositHistoryV2`, `GET /v1/withdrawal`,
`GET /v1/withdrawal/{getBankCodeList,getAllAccounts}`. The PDF report endpoints
return bytes for the in-app viewer.

### Account opening

`aof-mobile.nextcapital.com.pk` — AOF and document upload. Not exercised.

### FinBot

`finbot.finqalab.com` — chat assistant. Not exercised.

## Constants found in the app

Three groups, in `config.py`.

**Order codes.** Numeric strings, not enums:

| Code | Meaning |
|------|---------|
| `140` / `141` / `142` / `143` | limit / market / stop / stop-limit |
| `REG` / `ODD` / `AH` | regular board / odd lot / after hours |
| `Buy` / `Sell` | side, capitalised |
| `111` | `orderProperty`, normal |
| `W` | `orignateSource` |

**WebSocket path segments.** `oms_user_id` `291` and `session_token` `4rjrnta5`
are baked into the app and used by every client. They are **not per-user
credentials** — they are shared, fixed identifiers, and have been stable for
years. They do not authenticate anyone on their own; the STOMP `CONNECT` frame
carries the real credentials.

**AES key and IV.** A 32-byte key and 16-byte IV, hardcoded, used for the login
password and for `trading_pin_code`, `mobileNo`, `cnic`, `ibn_number` in the
profile. Disclosed in [`SECURITY.md`](../../SECURITY.md) — read that before
sending anything through it. Full protocol in
[03-protocols.md](03-protocols.md).

## Date and number conventions

Inconsistent, and a frequent source of silent wrong answers.

| Context | Format |
|---------|--------|
| `statistics()` query | `DD-MM-YYYY` |
| `graph()` query | `YYYY-MM-DD` |
| STOMP `fromDate`/`toDate` (trades) | `DD/MM/YYYY` |
| STOMP `trade_date` response | `YYYY-MM-DD` |
| Order-list `fromDate`/`toDate` | `HH:MM` |
| Payments `createdAt` | epoch **milliseconds** |
| Profile `cnic_expiry` | `DD/MM/YYYY` |

`sector` is a numeric PSX code (`0824` = Oil & Gas), not a label. Some numerics
arrive as JSON strings. `index_news`'s `lt` field is a JSON string *inside* the
JSON response.

## What the client deliberately does differently

Summarised here, detailed in [04-findings-and-decisions.md](04-findings-and-decisions.md):
`modify()` and `cancel()` are inferred and marked as such; watchlist reordering,
withdrawal V2, and 19 other paths are documented but not implemented; and the
`app_build` check is sent but never enforced by the server.
